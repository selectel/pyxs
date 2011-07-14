# -*- coding: utf-8 -*-
"""
    pyxs.client
    ~~~~~~~~~~~

    This module implements XenStore client, which uses multiple connection
    options for communication: :class:`UnixSocketConnection` and
    :class:`XenBusConnection`. Note however, that the latter one is
    not yet complete and should not be used, unless you know what
    you're doing.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import absolute_import

__all__ = ["Client", "UnixSocketConnection", "XenBusConnection"]

import errno
import os
import platform
import socket
from collections import deque

from ._internal import Event, Packet, Op
from .exceptions import ConnectionError, UnexpectedPacket, PyXSError
from .helpers import spec


#: A reverse mapping for :data:`errno.errorcode`.
_codeerror = dict((message, code)
                  for code, message in errno.errorcode.iteritems())


class FileDescriptorConnection(object):
    fd = None

    def __init__(self):
        raise NotImplemented("__init__() should be overriden by subclasses.")

    def disconnect(self):
        if self.fd is None:
            return

        try:
            os.close(self.fd)
        except OSError:
            pass
        finally:
            self.fd = None

    def send(self, packet):
        if not self.fd:
            self.connect()

        try:
            return os.write(self.fd, str(packet))
        except OSError as e:
            if e.args[0] is errno.EPIPE:
                self.disconnect()

            raise ConnectionError("Error while writing to {0!r}: {1}"
                                  .format(self.path, e.args))

    def recv(self):
        try:
            data = os.read(self.fd, Packet._struct.size)
        except OSError as e:
            if e.args[0] is errno.EPIPE:
                self.disconnect()

            raise ConnectionError("Error while reading from {0!r}: {1}"
                                  .format(self.path, e.args))
        else:
            op, rq_id, tx_id, size = Packet._struct.unpack(data)
            return Packet(op, os.read(self.fd, size), rq_id, tx_id)



class UnixSocketConnection(FileDescriptorConnection):
    """XenStore connection through Unix domain socket.

    :param str path: path to XenStore unix domain socket, if not
                     provided explicitly is restored from process
                     environment -- similar to what ``libxs`` does.
    :param float socket_timeout: see :func:`socket.settimeout` for
                                 details.
    """
    def __init__(self, path=None, socket_timeout=None):
        if path is None:
            path = (
                os.getenv("XENSTORED_PATH") or
                os.path.join(os.getenv("XENSTORED_RUNDIR",
                                       "/var/run/xenstored"), "socket")
            )

        self.path = path
        self.socket_timeout = None

    @property
    def args(self):
        return {"unix_socket_path": self.path,
                "socket_timeout": self.socket_timeout}

    def connect(self):
        if self.fd:
            return

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.socket_timeout)
            sock.connect(self.path)
        except socket.error as e:
            raise ConnectionError("Error connecting to {0!r}: {1}"
                                  .format(self.path, e.args))
        else:
            self.fd = sock.fileno()


class XenBusConnection(FileDescriptorConnection):
    """XenStore connection through XenBus.

    :param str path: path to XenBus block device; a predefined
                     OS-specific constant is used, if a value isn't
                     provided explicitly.
    """
    def __init__(self, path=None):
        if path is None:
            # .. note:: it looks like OCaml-powered ``xenstored``
            # simply ignores the posibility of being launched on a
            # platform, different from Linux, but ``libxs``  has those
            # constants in-place.
            system = platform.system()

            if system == "Linux":
                path = "/proc/xen/xenbus"
            elif system == "NetBSD":
                path = "/kern/xen/xenbus"
            else:
                path = "/dev/xen/xenbus"

        self.path = path

    @property
    def args(self):
        return {"xen_bus_path": self.path}

    def connect(self):
        if self.fd:
            return

        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except OSError as e:
            raise ConnectionError("Error while opening {0!r}: {1}"
                                  .format(self.path, e.args))


class Client(object):
    """XenStore client -- <useful comment>.

    :param str xen_bus_path: path to XenBus device, implies that
                             :class:`XenBusConnection` is used as a
                             backend.
    :param str unix_socket_path: path to XenStore Unix domain socket,
                                 usually something like
                                 ``/var/run/xenstored/socket`` -- implies
                                 that :class:`UnixSocketConnection` is
                                 used as a backend.
    :param float socket_timeout: see :func:`socket.settimeout` for
                                 details.
    :param bool transaction: if ``True`` :meth:`transaction_start` will
                             be issued right after connection is
                             established.

    .. note:: :class:`UnixSocketConnection` is used as a fallback value,
              if backend cannot be determined from arguments given.

    Here's a quick example:

    >>> with Client() as c:
    ...     c.write("/foo/bar", "baz")
    ...     c.read("/foo/bar")
    'OK'
    'baz'
    """
    def __init__(self, unix_socket_path=None, socket_timeout=None,
                 xen_bus_path=None, transaction=None):
        if unix_socket_path or not xen_bus_path:
            self.connection = UnixSocketConnection(
                unix_socket_path, socket_timeout=socket_timeout)
        else:
            self.connection = XenBusConnection(xen_bus_path)

        self.tx_id = 0
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

    def communicate(self, op, *args):
        self.connection.send(Packet(op, "".join(args), tx_id=self.tx_id))

        packet = self.connection.recv()

        # According to ``xenstore.txt`` erroneous responses start with
        # a capital E and end with ``NULL``-byte.
        if packet.op is Op.ERROR:
            error = _codeerror.get(packet.payload[:-1], 0)
            raise PyXSError(error, os.strerror(error))
        # Incoming packet should either be a watch event or have the
        # same operation type as the packet sent.
        elif packet.op is Op.WATCH_EVENT:
            self.events.append(packet)
        elif packet.op is not op:
            raise UnexpectedPacket(packet)
        # Making sure sent and recieved packets are within the same
        # transaction.
        elif self.tx_id and packet.tx_id is not self.tx_id:
            raise UnexpectedPacket(packet)

        return packet

    def command(self, *args):
        return self.communicate(*args).payload

    def ack(self, *args):
        if self.command(*args) != "OK\x00":
            raise PyXSError("Ooops ...")

    # Public API.
    # ...........

    @spec("<path>|")
    def read(self, path):
        """Reads data from a given path.

        :param str path: a path to read from.
        """
        return self.command(Op.READ, path)

    @spec("<path>|", "<value|>")
    def write(self, path, value):
        """Writes data to a given path.

        :param value: data to write (can be of any type, but will be
                      coerced to :func:`bytes` eventually).
        :param str path: a path to write to.
        """
        self.ack(Op.WRITE, path, value)

    @spec("<path>|")
    def mkdir(self, path):
        """Ensures that a given path exists, by creating it and any
        missing parents with empty values. If `path` or any parent
        already exist, its value is left unchanged.

        :param str path: path to directory to create.
        """
        self.ack(Op.MKDIR, path)

    @spec("<path>|")
    def rm(self, path):
        """Ensures that a given does not exist, by deleting it and all
        of its children. It is not an error if `path` doesn't exist, but
        it **is** an error if `path`'s immediate parent does not exist
        either.

        :param str path: path to directory to remove.
        """
        self.ack(Op.RM, path)

    @spec("<path>|")
    def directory(self, path):
        """Returns a list of names of the immediate children of `path`.
        The resulting children are each named as
        ``<path>/<child-leaf-name>``.

        :param str path: path to list.
        """
        return self.command(Op.DIRECTORY, path).rstrip("\x00").split("\x00")

    @spec("<path>|")
    def get_perms(self, path):
        """Returns a list of permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param str path: path to get permissions for.
        """
        return self.command(Op.GET_PERMS, path).rstrip("\x00").split("\x00")

    @spec("<path>|", "<perms>|+")
    def set_perms(self, path, perms):
        """Sets a access permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param str path: path to set permissions for.
        :param list perms: a list of permissions to set.
        """
        self.ack(Op.SET_PERMS, path, *perms)

    @spec("<wpath>|", "<token>|")
    def watch(self, wpath, token):
        """Adds a watch.

        When a `path` is modified (including path creation, removal,
        contents change or permissions change) this generates an event
        on the changed `path`. Changes made in transactions cause an
        event only if and when committed.

        :param str wpath: path to watch.
        :param str token: watch token, returned in watch notification.
        """
        self.ack(Op.WATCH, wpath, token)

    @spec("<wpath>|", "<token>|")
    def unwatch(self, wpath, token):
        """Removes a previously added watch.

        :param str wpath: path to unwatch.
        :param str token: watch token, passed to :meth:`watch`.
        """
        self.ack(Op.UNWATCH, wpath, token)

    def wait(self):
        """Waits for any of the watched paths to generate an event,
        which is a ``(path, token)`` pair, where the first element
        is event path, i.e. the actual path that was modified and
        second element is a token, passed to the :meth:`watch`.
        """
        if self.events:
            return self.events.popleft()

        while True:
            packet = self.connection.recv()

            if packet.op is Op.WATCH_EVENT:
                return Event(*packet.payload.rstrip("\x00").split("\x00"))

    @spec("<domid>|")
    def get_domain_path(self, domid):
        """Returns the domain's base path, as is used for relative
        transactions: ex: ``"/local/domain/<domid>"``. If a given
        `domid` doesn't exists the answer is undefined.

        :param int domid: domain to get base path for.
        """
        return self.command(Op.GET_DOMAIN_PATH, domid)

    @spec("<domid>|")
    def is_domain_introduced(self, domid):
        """Returns ``True` if ``xenstored`` is in communication with
        the domain; that is when `INTRODUCE` for the domain has not
        yet been followed by domain destruction or explicit
        `RELEASE`; and ``False`` otherwise.

        :param int domid: domain to check status for.
        """
        return {
            "T": True,
            "F": False
        }.get(self.command(Op.IS_DOMAIN_INTRODUCED, domid).rstrip("\x00"))

    @spec("<domid>|", "<mfn>|", "<eventchn>|")
    def introduce(self, domid, mfn, eventchn):
        """Tells ``xenstored`` to communicate with this domain.

        :param int domid: a real domain id, (``0`` is forbidden).
        :param long mfn: address of xenstore page in `domid`.
        :param int eventch: an unbound event chanel in `domid`.
        """
        self.ack(Op.INTRODUCE, domid, mfn, eventchn)

    @spec("<domid>|")
    def release(self, domid):
        """Manually requests ``xenstored`` to disconnect from the
        domain.

        :param int domid: domain to disconnect.

        .. note:: ``xenstored`` will in any case detect domain
                  destruction and disconnect by itself.

        .. todo:: make sure it's only executed from Dom0.
        """
        self.ack(Op.RELEASE, domid)

    @spec("<domid>|")
    def resume(self, domid):
        """Tells ``xenstored`` to clear its shutdown flag for a
        domain. This ensures that a subsequent shutdown will fire the
        appropriate watches.

        :param int domid: domain to resume.

        .. todo:: make sure it's only executed from Dom0.
        """
        self.ack(Op.RESUME, domid)

    @spec("<domid>|", "<tdomid>|")
    def set_target(self, domid, target):
        """Tells ``xenstored`` that a domain is targetting another one,
        so it should let it tinker with it. This grants domain `domid`
        full access to paths owned by `target`. Domain `domid` also
        inherits all permissions granted to `target` on all other
        paths.

        :param int domid: domain to set target for.
        :param int target: target domain (yours truly, Captain).

        .. todo:: make sure it's only executed from Dom0.
        """
        self.ack(Op.SET_TARGET, domid, target)

    def transaction_start(self):
        """Starts a new transaction and returns transaction handle, which
        is simply an int.

        .. warning::

           Currently ``xenstored`` has a bug that after 2^32 transactions
           it will allocate id 0 for an actual transaction.
        """
        return int(self.command(Op.TRANSACTION_START, "\x00") .rstrip("\x00"))


    def transaction_end(self, commit=True):
        """End a transaction currently in progress; if no transaction is
        running no command is sent to XenStore.
        """
        if self.tx_id:
            self.ack(Op.TRANSACTION_END, ["F", "T"][commit] + "\x00")
            self.tx_id = 0

    def transaction(self):
        if self.tx_id:
            raise PyXSError(errno.EALREADY, os.strerror(errno.EALREADY))

        return Client(transaction=True, **self.connection.args)
