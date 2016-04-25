# -*- coding: utf-8 -*-
"""
    pyxs.client
    ~~~~~~~~~~~

    This module implements XenStore client, which can communicate with
    XenStore either via: :class:`~pyxs.connection.UnixSocketConnection`
    or :class:`~pyxs.connection.XenBusConnection`.

    :copyright: (c) 2011 by Selectel.
    :copyright: (c) 2016 by pyxs authors and contributors, see AUTHORS
                for more details.
    :license: LGPL, see LICENSE for more details.
"""

from __future__ import absolute_import

__all__ = ["Router", "Client", "Monitor"]

import copy
import errno
import posixpath
import re
import socket
import select
import sys
import threading
from collections import defaultdict
from functools import partial

try:
    import Queue as queue
except ImportError:
    import queue

# XXX see ``Router`` docstring for motivation.
if sys.version_info[:2] < (3, 2):
    _condition_wait = partial(threading._Condition.wait, timeout=1)
else:
    _condition_wait = threading.Condition.wait

from ._internal import NUL, Event, Packet, Op, next_rq_id
from .connection import UnixSocketConnection, XenBusConnection
from .exceptions import UnexpectedPacket, ConnectionError, PyXSError
from .helpers import check_path, check_watch_path, check_perms, error

_re_7bit_ascii = re.compile(b"^[\x00\x20-\x7f]+$")


class Router(object):
    """Router.

    The goal of the router is to multiplex XenStore connection between
    multiple clients and monitors.

    .. versionadded: 0.4.0

    :param connection FileDescriptorConnection:
        owned by the router. The connection is open when the router is
        started and remains open until the router is terminated.

    .. note::

       Python lacks API for interrupting a thread from another thread.
       This means that when a router cannot be stopped when it is blocked
       in :func:`select.select` or :meth:`~threading.Condition.wait`.

       The following two "hacks" are used to ensure prompt termination.

       1. A router is equipped with a :func:`socket.socketpair`. The
          reader-end of the pair is selected in the mainloop alongside
          the XenStore connection, while the writer-end is used in
          :meth:`~pyxs.client.Router.terminate` to force-stop the mainloop.
       2. All operations with :class:`threading.Condition` variables user
          a 1 second timeout. This "hack" is only relevant for Python
          prior to 3.2 which didn't allow to interrupt lock acquisitions.
          See `issue8844`_ on CPython issue tracker for details. On
          Python 3.2 and later no timeout is used.

        .. _issue8844: https://bugs.python.org/issue8844
    """
    def __init__(self, connection):
        self.r_terminator, self.w_terminator = socket.socketpair()
        self.connection = connection
        self.send_lock = threading.Lock()
        self.rvars = {}
        self.monitors = defaultdict(list)

        # Router thread is daemonic to prevent blocking in case
        # the client wasn't finilzed properly, e.g. unhandled
        # exception outside of ``with``. As a result, we cannot
        # guarantee data integrity unless either ``close`` or
        # ``__exit__`` was closed.
        self.thread = threading.Thread(target=self)
        self.thread.daemon = True

    def __repr__(self):
        return "Router({0})".format(self.connection)

    def __call__(self):
        try:
            while True:
                rlist, _wlist, _xlist = select.select(
                    [self.connection, self.r_terminator], [], [])
                if not rlist:
                    continue
                elif self.r_terminator in rlist:
                    break

                packet = self.connection.recv()
                if packet.op == Op.WATCH_EVENT:
                    event = Event(*packet.payload.split(NUL)[:-1])
                    for monitor in self.monitors[event.token]:
                        monitor.events.put(event)
                else:
                    rvar = self.rvars.pop(packet.rq_id, None)
                    if rvar is None:
                        raise UnexpectedPacket(packet)
                    else:
                        rvar.set(packet)
        finally:
            self.connection.close()
            self.r_terminator.close()
            self.w_terminator.close()

    @property
    def is_connected(self):
        """Checks if the underlying connection is active."""
        return self.connection.is_connected

    def subscribe(self, token, monitor):
        """Subscribes a ``monitor`` from events with a given ``token``."""
        self.monitors[token].append(monitor)

    def unsubscribe(self, token, monitor):
        """Unsubscribes a ``monitor`` to events with a given ``token``."""
        self.monitors[token].remove(monitor)

    def send(self, packet):
        """Sends a packet to XenStore.

        :returns RVar: a reference to the XenStore response.
        """
        with self.send_lock:
            # The order here matters. XenStore might reply to the packet
            # *before* the ``rvar`` is registered.
            self.rvars[packet.rq_id] = rvar = RVar()
            self.connection.send(packet)
            return rvar

    def start(self):
        """Starts the router thread.

        Does nothing if the router is already started.
        """
        # Connection is deliberately done in the calling thread so that
        # ``ConnectionError`` could be handled. See issue #8 on GitHub
        # for details.
        self.connection.connect()

        if not self.thread.is_alive():
            self.thread.start()

        while not self.is_connected:
            if not self.thread.is_alive():
                raise ConnectionError("router died")

    def terminate(self):
        """Terminates the router.

        After termination the router can no longer send or receive packets.
        Does nothing if the router was already terminated.
        """
        if self.is_connected:
            self.w_terminator.sendall(NUL)

        if self.thread.is_alive():
            self.thread.join()


class RVar(object):
    """A thread-safe shared mutable reference.

    .. versionadded:: 0.4.0
    """
    __slots__ = ["condition", "target"]

    def __init__(self):
        self.condition = threading.Condition()
        self.target = None

    def __repr__(self):
        return "RVar({0})".format(self.target)

    def get(self):
        """Blocks until the value is :meth:`set`` and then returns the value.

        .. note:: The returned value is guaranteed never to be ``None``.
        """
        with self.condition:
            while self.target is None:
                _condition_wait(self.condition)

        return self.target

    def set(self, target):
        """Sets the value, which effectively unblocks all :meth:`get` calls."""
        with self.condition:
            self.target = target
            self.condition.notify_all()


class Client(object):
    """XenStore client.

    :param str unix_socket_path: path to XenStore Unix domain socket.
    :param str xen_bus_path: path to XenBus device.

    If ``unix_socket_path`` is given or :class:`~pyxs.client.Client`
    was created with no arguments, XenStore is accessed via
    :class:`~pyxs.connection.UnixSocketConnection`; otherwise,
    :class:`~pyxs.connection.XenBusConnection` is used.

    Each client has a :class:`~pyxs.client.Router` thread running
    in the background. The goal of the router is to multiplex
    requests from different transaction through a single XenStore
    connection.

    .. versionchanged:: 0.4.0

       The constructor no longer accepts ``connection`` argument. If
       you wan't to force the use of a specific connection class, wrap
       it in a :class:`~pyxs.client.Router`::

            from pyxs import Router, Client
            from pyxs.connection import XenBusConnection

            router = Router(XenBusConnection())
            with Client(router=router) as c:
                do_something(c)

    .. warning::

       Always finalize the client either explicitly by calling
       :meth:`~pyxs.client.Client.close` or implicitly via
       a context manager to prevent data loss.

    .. seealso::

       `Xenstore protocol specification \
       <http://xenbits.xen.org/docs/4.4-testing/misc/xenstore.txt>`_
       for a description of the protocol, implemented by ``Client``.
    """
    #: A flag, which is ``True`` if we're operating on control domain
    #: and else otherwise.
    try:
        SU = open("/proc/xen/capabilities", "rb").read() == b"control_d\n"
    except (IOError, OSError):
        SU = False

    def __init__(self, unix_socket_path=None, xen_bus_path=None, router=None):
        if router is None:
            if unix_socket_path or not xen_bus_path:
                connection = UnixSocketConnection(unix_socket_path)
            else:
                connection = XenBusConnection(xen_bus_path)

            router = Router(connection)

        self.router = router
        self.tx_id = 0

    def __repr__(self):
        return "Client({0})".format(self.router.connection)

    def __copy__(self):
        return self.__class__(router=self.router)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.close()

        if self.tx_id and not any(exc_info):
            raise PyXSError("uncommitted transaction")

    # Private API.
    # ............

    def execute_command(self, op, *args, **kwargs):
        if not all(map(_re_7bit_ascii.match, args)):
            raise ValueError(args)

        kwargs.update(tx_id=self.tx_id, rq_id=next_rq_id())
        rvar = self.router.send(Packet(op, b"".join(args), **kwargs))
        packet = rvar.get()
        if packet.op == Op.ERROR:
            # Erroneous responses are POSIX error code ending with a
            # ``NUL`` byte.
            raise error(packet.payload[:-1])
        elif packet.op != op or packet.tx_id != self.tx_id:
            raise UnexpectedPacket(packet)

        return packet.payload.rstrip(NUL)

    def ack(self, *args):
        payload = self.execute_command(*args)
        if payload != b"OK":
            raise PyXSError(payload)

    # Public API.
    # ...........

    def connect(self):
        """Connects to the XenStore daemon.

        :raises pyxs.exceptions.ConnectionError: if the connection could
            not be opened. This could happen either because XenStore is
            not running on the machine or due to the lack of permissions.

        .. versionadded: 0.4.0

        .. warning:: This method is unsafe. Please use client as a context
                     manager to ensure it is properly finalized.
        """
        self.router.start()

    def close(self):
        """Finalizes the client.

        .. warning:: This method is unsafe. Please use client as a context
                     manager to ensure it is properly finalized.
        """
        self.router.terminate()

    def read(self, path, default=None):
        """Reads data from a given path.

        :param bytes path: a path to read from.
        :param bytes default: default value, to be used if `path` doesn't
                              exist.
        """
        check_path(path)
        try:
            return self.execute_command(Op.READ, path + NUL)
        except PyXSError as e:
            if e.args[0] == errno.ENOENT and default is not None:
                return default

            raise

    __getitem__ = read

    def write(self, path, value):
        """Writes data to a given path.

        :param bytes value: data to write.
        :param bytes path: a path to write to.
        """
        check_path(path)
        self.ack(Op.WRITE, path + NUL, value)

    __setitem__ = write

    def mkdir(self, path):
        """Ensures that a given path exists, by creating it and any
        missing parents with empty values. If `path` or any parent
        already exist, its value is left unchanged.

        :param bytes path: path to directory to create.
        """
        check_path(path)
        self.ack(Op.MKDIR, path + NUL)

    def delete(self, path):
        """Ensures that a given does not exist, by deleting it and all
        of its children. It is not an error if `path` doesn't exist, but
        it **is** an error if `path`'s immediate parent does not exist
        either.

        :param bytes path: path to directory to remove.
        """
        check_path(path)
        self.ack(Op.RM, path + NUL)

    __delitem__ = delete

    def list(self, path):
        """Returns a list of names of the immediate children of `path`.

        :param bytes path: path to list.
        """
        check_path(path)
        payload = self.execute_command(Op.DIRECTORY, path + NUL)
        return [] if not payload else payload.split(NUL)

    def exists(self, path):
        """Checks if a given `path` exists.

        :param bytes path: path to check.
        """
        try:
            self.list(path)
        except PyXSError as e:
            if e.args[0] == errno.ENOENT:
                return False

            raise
        else:
            return True

    def get_perms(self, path):
        """Returns a list of permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param bytes path: path to get permissions for.
        """
        check_path(path)
        payload = self.execute_command(Op.GET_PERMS, path + NUL)
        return payload.split(NUL)

    def set_perms(self, path, perms):
        """Sets a access permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param bytes path: path to set permissions for.
        :param list perms: a list of permissions to set.
        """
        check_path(path)
        check_perms(perms)
        self.ack(Op.SET_PERMS, path + NUL, *(perm + NUL for perm in perms))

    def walk(self, top, topdown=True):
        """Walk XenStore, yielding 3-tuples ``(path, value, children)``
        for each node in the tree, rooted at node `top`.

        :param bytes top: node to start from.
        :param bool topdown: see :func:`os.walk` for details.
        """
        children = self.list(top)

        try:
            value = self.read(top)
        except PyXSError:
            value = b""  # '/' or no read permissions?

        if topdown:
            yield top, value, children

        for child in children:
            for x in self.walk(posixpath.join(top, child)):
                yield x

        if not topdown:
            yield top, value, children

    def get_domain_path(self, domid):
        """Returns the domain's base path, as used for relative
        requests: e.g. ``b"/local/domain/<domid>"``. If a given
        `domid` doesn't exists the answer is undefined.

        :param int domid: domain to get base path for.
        """
        return self.execute_command(Op.GET_DOMAIN_PATH,
                                    str(domid).encode() + NUL)

    def is_domain_introduced(self, domid):
        """Returns ``True`` if ``xenstored`` is in communication with
        the domain; that is when `INTRODUCE` for the domain has not
        yet been followed by domain destruction or explicit
        `RELEASE`; and ``False`` otherwise.

        :param int domid: domain to check status for.
        """
        payload = self.execute_command(Op.IS_DOMAIN_INTRODUCED,
                                       str(domid).encode() + NUL)
        return {b"T": True, b"F": False}[payload]

    def introduce_domain(self, domid, mfn, eventchn):
        """Tells ``xenstored`` to communicate with this domain.

        :param int domid: a real domain id, (``0`` is forbidden).
        :param int mfn: address of xenstore page in `domid`.
        :param int eventchn: an unbound event chanel in `domid`.
        """
        if not domid:
            raise ValueError("domain 0 cannot be introduced.")

        self.ack(Op.INTRODUCE,
                 str(domid).encode() + NUL,
                 str(mfn).encode() + NUL,
                 str(eventchn).encode() + NUL)

    def release_domain(self, domid):
        """Manually requests ``xenstored`` to disconnect from the
        domain.

        :param int domid: domain to disconnect.

        .. note:: ``xenstored`` will in any case detect domain
                  destruction and disconnect by itself.
        """
        if not self.SU:
            raise error(errno.EPERM)

        self.ack(Op.RELEASE, str(domid).encode() + NUL)

    def resume_domain(self, domid):
        """Tells ``xenstored`` to clear its shutdown flag for a
        domain. This ensures that a subsequent shutdown will fire the
        appropriate watches.

        :param int domid: domain to resume.
        """
        if not self.SU:
            raise error(errno.EPERM)

        self.ack(Op.RESUME, str(domid).encode() + NUL)

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

        self.ack(Op.SET_TARGET, str(domid).encode() + NUL,
                 str(target).encode() + NUL)

    def transaction(self):
        """Starts a new transaction.

        :returns int: transaction handle.
        :raises pyxs.exceptions.PyXSError:
            with :data:`errno.EALREADY` if this client is already in
            a transaction.

        .. warning::

           Currently ``xenstored`` has a bug that after 2**32 transactions
           it will allocate id 0 for an actual transaction.
        """
        if self.tx_id:
            raise error(errno.EALREADY)

        payload = self.execute_command(Op.TRANSACTION_START, NUL)
        self.tx_id = int(payload)
        return self.tx_id

    def rollback(self):
        """Rolls back a transaction currently in progress.

        .. versionchanged: 0.4.0

           In previous versions the method gracefully handled attempts to
           end a transaction when no transaction was running. This is no
           longer the case. The method will send the corresponding command
           to XenStore.
        """
        self.ack(Op.TRANSACTION_END, b"F" + NUL)
        self.tx_id = 0

    def commit(self):
        """Commits a transaction currently in progress.

        :returns bool: ``False`` if commit failed because of the
                       intervening writes and ``True`` otherwise. In any
                       case transaction is invalidated. The caller is
                       responsible for starting a new transaction, repeating
                       all of the operations a re-committing.

        .. versionchanged: 0.4.0

           In previous versions the method gracefully handled attempts to
           end a transaction when no transaction was running. This is no
           longer the case. The method will send the corresponding command
           to XenStore.
        """
        try:
            self.ack(Op.TRANSACTION_END, b"T" + NUL)
        except PyXSError as e:
            if e.args[0] == errno.EAGAIN:
                return False

            raise
        else:
            return True
        finally:
            self.tx_id = 0

    def monitor(self):
        """Returns a new :class:`Monitor` instance, which is currently
        the only way of doing PUBSUB.

        The monitor shares the router with its parent client. Thus closing
        the client invalidates the monitor. Closing the monitor, on the
        other hand, had no effect on the router state.

        .. note::

           Using :meth:`monitor` over
           :class:`~pyxs.connection.XenBusConnection` is currently
           unsupported, because XenBus does not obey XenStore protocol
           specification. See `xen-devel`_ discussion for details.

            .. _xen-devel: \
               http://lists.xen.org/archives/html/xen-devel/2016-02/msg03737
        """
        if isinstance(self.router.connection, XenBusConnection):
            raise PyXSError("using ``Monitor`` over XenBus is not supported",
                            UserWarning)

        return Monitor(copy.copy(self))


class Monitor(object):
    """Monitor implements minimal PUBSUB functionality on top of XenStore.

    >>> with Client() as c:
    ...    m = c.monitor():
    ...    m.watch("foo/bar")
    ...    print(next(c.wait()))
    Event(...)

    :param Client client: a reference to the parent client.

    .. note::

       When used as a context manager the monitor will try to unwatch
       all watched paths.
    """
    def __init__(self, client):
        self.client = client
        self.events = queue.Queue()
        self.unwatch_queue = set()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    @property
    def watched(self):
        """A set of paths currently watched by the monitor."""
        return set(wpath for wpath, token in self.unwatch_queue)

    def close(self):
        """Finalizes the monitor by unwatching all watched paths."""
        for wpath, token in list(self.unwatch_queue):
            self.unwatch(wpath, token)

    def watch(self, wpath, token):
        """Adds a watch.

        Any alteration to the watched path generates an event. This
        includes path creation, removal, contents change or permission
        change. An event can also be triggered spuriously.

        Changes made in transactions cause an event only if and when
        committed.

        :param bytes wpath: path to watch.
        :param bytes token: watch token, returned in watch notification.
        """
        check_watch_path(wpath)
        self.client.router.subscribe(token, self)
        self.client.ack(Op.WATCH, wpath + NUL, token + NUL)
        self.unwatch_queue.add((wpath, token))

    def unwatch(self, wpath, token):
        """Removes a previously added watch.

        :param bytes wpath: path to unwatch.
        :param bytes token: watch token, passed to :meth:`watch`.
        """
        check_watch_path(wpath)
        self.client.ack(Op.UNWATCH, wpath + NUL, token + NUL)
        self.client.router.unsubscribe(token, self)
        self.unwatch_queue.discard((wpath, token))

    def wait(self, unwatched=False):
        """Yields events for all of the watched paths.

        An event is a ``(path, token)`` pair, where the first element
        is event path, i.e. the actual path that was modified, and the
        second -- a token, passed to :meth:`watch`.

        :param bool unwatched: if ``True`` :meth:`wait` might yield
                               spurious unwatched packets, otherwise
                               these are dropped. Defaults to ``False``.
        """
        while True:
            with self.events.not_empty:
                while not self.events._qsize():
                    _condition_wait(self.events.not_empty)

            event = wpath, token = self.events.get_nowait()

            # Check that event path or its parent is watched.
            while wpath and (wpath, token) not in self.unwatch_queue:
                wpath = posixpath.dirname(wpath)

            if wpath or unwatched:
                yield event
