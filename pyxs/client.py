# -*- coding: utf-8 -*-
"""
    pyxs.client
    ~~~~~~~~~~~

    This module implements XenStore client, which uses multiple connection
    options for communication: :class:`.connection.UnixSocketConnection`
    and :class:`.connection.XenBusConnection`. Note however, that the
    latter one can be a bit buggy, when dealing with ``WATCH_EVENT``
    packets, so using :class:`.connection.UnixSocketConnection` is
    preferable.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import absolute_import, unicode_literals

__all__ = ["Client", "Monitor"]

import copy
import errno
import re
import threading
import time
import posixpath
from collections import deque

from ._internal import Event, Packet, Op
from .connection import UnixSocketConnection, XenBusConnection
from .exceptions import UnexpectedPacket, PyXSError
from .helpers import validate_path, validate_watch_path, validate_perms, \
    dict_merge, force_unicode, error


class Client(object):
    """XenStore client -- <useful comment>.

    :param str xen_bus_path: path to XenBus device, implies that
                             :class:`~pyxs.connection.XenBusConnection`
                             is used as a backend.
    :param str unix_socket_path: path to XenStore Unix domain socket,
        usually something like ``/var/run/xenstored/socket`` -- implies
        that :class:`~pyxs.connection.UnixSocketConnection` is used
        as a backend.
    :param float socket_timeout: see :meth:`~socket.socket.settimeout`
                                 for details.
    :param bool transaction: if ``True`` :meth:`transaction_start` will
                             be issued right after connection is
                             established.

    .. note:: :class:`~pyxs.connection.UnixSocketConnection` is used
              as a fallback value, if backend cannot be determined
              from arguments given.

    Here's a quick example:

    >>> with Client() as c:
    ...     c.write("/foo/bar", "baz")
    ...     c.read("/foo/bar")
    'OK'
    'baz'
    """
    COMMAND_VALIDATORS = dict_merge(
        dict.fromkeys([Op.READ, Op.MKDIR, Op.RM, Op.DIRECTORY, Op.GET_PERMS],
                      validate_path),
        dict.fromkeys([Op.WRITE], lambda p, v: validate_path(p)),
        dict.fromkeys([Op.SET_PERMS],
            lambda p, *perms: validate_path(p) and validate_perms(perms)),
        dict.fromkeys([Op.GET_DOMAIN_PATH, Op.IS_DOMAIN_INTRODUCED,
                       Op.INTRODUCE, Op.RELEASE, Op.SET_TARGET],
            lambda *domids: all(d[:-1].isdigit() for d in domids)),
        dict.fromkeys([Op.WATCH, Op.UNWATCH],
            lambda p, t: validate_path(p) and validate_watch_path(p))
    )

    #: A flag, which is ``True`` if we're operating on control domain
    #: and else otherwise.
    try:
        SU = open("/proc/xen/capabilities").read() == "control_d\n"
    except (IOError, OSError):
        SU = False

    def __init__(self, unix_socket_path=None, socket_timeout=None,
                 xen_bus_path=None, connection=None, transaction=None):
        if connection:
            self.connection = connection
        elif unix_socket_path or not xen_bus_path:
            self.connection = UnixSocketConnection(
                unix_socket_path, socket_timeout=socket_timeout)
        else:
            self.connection = XenBusConnection(xen_bus_path)

        self.tx_id = 0
        self.tx_lock = threading.Lock()
        self.events = deque()

        if transaction:  # Requesting a new transaction id.
            self.tx_id = self.transaction_start()

    def __enter__(self):
        self.connection.connect()
        return self

    def __exit__(self, *exc_info):
        if not any(exc_info) and self.tx_id:
            self.transaction_end(commit=True)

        self.connection.disconnect()

    # Private API.
    # ............

    def execute_command(self, op, *args, **kwargs):
        args = [force_unicode(arg) + "\x00" for arg in args]

        if not self.COMMAND_VALIDATORS.get(op, lambda *args: True)(*args):
            raise ValueError(args)
        elif not all(re.match("^[\x00\x20-\x7f]+$", arg) for arg in args):
            raise ValueError(args)

        with self.tx_lock:
            kwargs["tx_id"] = self.tx_id  # Forcing ``tx_id`` here.
            self.connection.send(Packet(op, "".join(args), **kwargs))

            # If we have any watched paths `XenStore` will send watch
            # events mixed with replies to other operations, so we loop
            # until we recieve a packet with an expected operation type.
            while True:
                packet = self.connection.recv()

                # According to ``xenstore.txt`` erroneous responses start
                # with a capital E and end with ``NULL``-byte.
                if packet.op is Op.ERROR:
                    raise error(packet.payload[:-1])
                # Incoming packet should either be a watch event or have
                # the same operation type as the packet sent.
                elif packet.op is Op.WATCH_EVENT:
                    self.events.append(packet)
                elif packet.op is not op:
                    raise UnexpectedPacket(packet)
                # Making sure sent and recieved packets are within the
                # same transaction -- not relevant for `XenBusConnection`,
                # for some reason it sometimes returns *random* values
                # of tx_id and rq_id.
                elif (not isinstance(self.connection, XenBusConnection) and
                      packet.tx_id is not self.tx_id):
                    raise UnexpectedPacket(packet)
                else:
                    break

        return packet.payload.rstrip("\x00")

    def ack(self, *args):
        if self.execute_command(*args) != "OK":
            raise PyXSError("Ooops ...")

    # Public API.
    # ...........

    def read(self, path, default=None):
        """Reads data from a given path.

        :param str path: a path to read from.
        :param str default: default value, to be used if `path` doesn't
                            exist.
        """
        try:
            return self.execute_command(Op.READ, path)
        except PyXSError as e:
            if e.args[0] is errno.ENOENT and default is not None:
                return default

            raise

    __getitem__ = read

    def write(self, path, value):
        """Writes data to a given path.

        :param value: data to write (can be of any type, but will be
                      coerced to :func:`bytes` eventually).
        :param str path: a path to write to.
        """
        self.ack(Op.WRITE, path, value)

    __setitem__ = write

    def mkdir(self, path):
        """Ensures that a given path exists, by creating it and any
        missing parents with empty values. If `path` or any parent
        already exist, its value is left unchanged.

        :param str path: path to directory to create.
        """
        self.ack(Op.MKDIR, path)

    def rm(self, path):
        """Ensures that a given does not exist, by deleting it and all
        of its children. It is not an error if `path` doesn't exist, but
        it **is** an error if `path`'s immediate parent does not exist
        either.

        :param str path: path to directory to remove.
        """
        self.ack(Op.RM, path)

    __delitem__ = rm

    def ls(self, path):
        """Returns a list of names of the immediate children of `path`.

        :param str path: path to list.
        """
        payload = self.execute_command(Op.DIRECTORY, path)
        return [] if payload is "" else payload.split("\x00")

    def get_permissions(self, path):
        """Returns a list of permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param str path: path to get permissions for.
        """
        payload = self.execute_command(Op.GET_PERMS, path)
        return payload.split("\x00")

    def set_permissions(self, path, perms):
        """Sets a access permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param str path: path to set permissions for.
        :param list perms: a list of permissions to set.
        """
        self.ack(Op.SET_PERMS, path, *perms)

    def walk(self, top, topdown=True):
        """Walk XenStore, yielding 3-tuples ``(path, value, children)``
        for each node in the tree, rooted at node `top`.

        :param str top: node to start from.
        :param bool topdown: see :func:`os.walk` for details.
        """
        try:
            children = self.ls(top)
        except PyXSError:
            return

        try:
            value = self.read(top)
        except PyXSError:
            value = ""  # '/' or no read permissions?

        if topdown:
            yield top, value, children

        for child in children:
            for x in self.walk(posixpath.join(top, child)):
                yield x

        if not topdown:
            yield top, value, children

    def get_domain_path(self, domid):
        """Returns the domain's base path, as is used for relative
        transactions: ex: ``"/local/domain/<domid>"``. If a given
        `domid` doesn't exists the answer is undefined.

        :param int domid: domain to get base path for.
        """
        return self.execute_command(Op.GET_DOMAIN_PATH, domid)

    def is_domain_introduced(self, domid):
        """Returns ``True`` if ``xenstored`` is in communication with
        the domain; that is when `INTRODUCE` for the domain has not
        yet been followed by domain destruction or explicit
        `RELEASE`; and ``False`` otherwise.

        :param int domid: domain to check status for.
        """
        payload = self.execute_command(Op.IS_DOMAIN_INTRODUCED, domid)
        return {"T": True, "F": False}[payload]

    def introduce_domain(self, domid, mfn, eventchn):
        """Tells ``xenstored`` to communicate with this domain.

        :param int domid: a real domain id, (``0`` is forbidden).
        :param long mfn: address of xenstore page in `domid`.
        :param int eventchn: an unbound event chanel in `domid`.
        """
        if not domid:
            raise ValueError("Dom0 cannot be introduced.")

        self.ack(Op.INTRODUCE, domid, mfn, eventchn)

    def release_domain(self, domid):
        """Manually requests ``xenstored`` to disconnect from the
        domain.

        :param int domid: domain to disconnect.

        .. note:: ``xenstored`` will in any case detect domain
                  destruction and disconnect by itself.
        """
        if not self.SU:
            raise error(errno.EPERM)

        self.ack(Op.RELEASE, domid)

    def resume_domain(self, domid):
        """Tells ``xenstored`` to clear its shutdown flag for a
        domain. This ensures that a subsequent shutdown will fire the
        appropriate watches.

        :param int domid: domain to resume.
        """
        if not self.SU:
            raise error(errno.EPERM)

        self.ack(Op.RESUME, domid)

    def set_target(self, domid, target):
        """Tells ``xenstored`` that a domain is targetting another one,
        so it should let it tinker with it. This grants domain `domid`
        full access to paths owned by `target`. Domain `domid` also
        inherits all permissions granted to `target` on all other
        paths.

        :param int domid: domain to set target for.
        :param int target: target domain (yours truly, Captain).
        """
        if not self.SU:
            raise error(errno.EPERM)

        self.ack(Op.SET_TARGET, domid, target)

    def transaction_start(self):
        """Starts a new transaction and returns transaction handle, which
        is simply an int.

        .. warning::

           Currently ``xenstored`` has a bug that after 2^32 transactions
           it will allocate id 0 for an actual transaction.
        """
        payload = self.execute_command(Op.TRANSACTION_START, "")
        return int(payload)

    def transaction_end(self, commit=True):
        """End a transaction currently in progress; if no transaction is
        running no command is sent to XenStore.
        """
        if self.tx_id:
            self.ack(Op.TRANSACTION_END, ["F", "T"][commit])
            self.tx_id = 0

    def monitor(self):
        """Returns a new :class:`Monitor` instance, which is currently
        *the only way* of doing PUBSUB.
        """
        return Monitor(connection=copy.copy(self.connection))

    def transaction(self):
        """Returns a new :class:`Client` instance, operating within a
        new transaction; can only be used only when no transaction is
        running. Here's an example:

        >>> with Client().transaction() as t:
        ...     t.do_something()
        ...     t.transaction_end(commit=True)

        However, the last line is completely optional, since the default
        behaviour is to commit everything on context manager exit.

        :raises pyxs.exceptions.PyXSError: if this client is linked to
                                           and active transaction.
        """
        if self.tx_id:
            raise error(errno.EALREADY)

        return Client(connection=copy.copy(self.connection),
                      transaction=True)


class Monitor(object):
    """XenStore monitor -- allows minimal PUBSUB-like functionality
    on top of XenStore.

    >>> m = Client().monitor()
    >>> m.watch("foo/bar")
    >>> m.wait()
    Event(...)
    """

    def __init__(self, connection):
        self.client = Client(connection=connection)

    def __enter__(self):
        self.client.__enter__()
        return self

    def __exit__(self, *args):
        self.client.__exit__(*args)

    def watch(self, wpath, token):
        """Adds a watch.

        When a `path` is modified (including path creation, removal,
        contents change or permissions change) this generates an event
        on the changed `path`. Changes made in transactions cause an
        event only if and when committed.

        :param str wpath: path to watch.
        :param str token: watch token, returned in watch notification.
        """
        self.client.ack(Op.WATCH, wpath, token)

    def unwatch(self, wpath, token):
        """Removes a previously added watch.

        :param str wpath: path to unwatch.
        :param str token: watch token, passed to :meth:`watch`.
        """
        self.client.ack(Op.UNWATCH, wpath, token)

    def wait(self, sleep=None):
        """Waits for any of the watched paths to generate an event,
        which is a ``(path, token)`` pair, where the first element
        is event path, i.e. the actual path that was modified and
        second element is a token, passed to the :meth:`watch`.

        :param float sleep: number of seconds to sleep between event
                            checks.
        """
        while True:
            if self.client.events:
                packet = self.client.events.popleft()
                return Event(*packet.payload.split("\x00")[:-1])

            # Executing a noop, hopefuly we'll get some events queued
            # in the meantime. Note: I know it sucks, but it seems like
            # there's no other way ...
            self.client.execute_command(Op.DEBUG, "")

            if sleep is not None:
                time.sleep(sleep)
