# -*- coding: utf-8 -*-
"""
    pyxs.client
    ~~~~~~~~~~~

    This module implements XenStore client, which uses Unix socket for
    communication.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import absolute_import

__all__ = ["Client", "UnixSocketConnection", "XenBusConnection"]

import errno
import os
import platform
import socket

from ._internal import Event, Packet, Op
from .exceptions import ConnectionError
from .helpers import spec


class UnixSocketConnection(object):
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
        self.socket = None
        self.socket_timeout = None

    def connect(self):
        if self.socket:
            return

        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.settimeout(self.socket_timeout)
            self.socket.connect(self.path)
        except socket.error as e:
            raise ConnectionError("Error connecting to {0}: {1}"
                                  .format(self.path, e))

    def disconnect(self):
        if self.socket is None:
            return

        try:
            self.socket.close()
        except socket.error:
            pass

        self.socket = None

    def send(self, packet):
        if not self.socket:
            self.connect()

        try:
            return self.socket.sendall(str(packet))
        except socket.error as e:
            if e.args[0] is errno.EPIPE:
                self.disconnect()

            raise ConnectionError("Error {0} while writing to socket: {1}"
                                  .format(e.args))

    def recv(self):
        chunks, done = [], False
        while not done:
            try:
                data = self.socket.recv(1024)
            except socket.error:
                done = True
            else:
                chunks.append(data)
                done = len(data) <= 1024
        else:
            return Packet.from_string("".join(chunks))


class XenBusConnection(object):
    """XenStore connection through XenBus.

    :param str path: path to XenBus block device; a predefined
                     OS-specific constant is used, if a value isn't
                     provided explicitly.
    """
    def __init__(self, path=None):
        if path is None:
            system = platform.system()

            if system == "Linux":
                path = "/proc/xen/xenbus"
            elif system == "NetBSD":
                path = "/kern/xen/xenbus"
            else:
                path = "/dev/xen/xenbus"

        self.path = path
        self.fd = None

    def connect(self):
        if self.fd:
            return

        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except (IOError, OSError) as e:
            raise ConnectionError("Error while opening {0}: {1}"
                                  .format(self.path, e))

    def disconnect(self):
        if self.fd is None:
            return

        try:
            os.close(self.fd)
        except OSError:
            pass

        self.fd = None

    def send(self, packet):
        if not self.fd:
            self.connect()

        try:
            os.write(self.fd, str(packet))
        except OSError as e:
            raise  # .. todo:: convert exception to `pyxs` format.

    def recv(self):
        try:
            return Packet.from_file(os.fdopen(self.fd))
        except OSError as e:
            raise  # .. todo:: convert exception to `pyxs` format.



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

    .. note:: :class:`UnixSocketConnection` is used as a fallback value,
              if backend cannot be determined from arguments given.
    """
    def __init__(self, xen_bus_path=None, unix_socket_path=None,
                 socket_timeout=None):
        if unix_socket_path or not xen_bus_path:
            self.connection = UnixSocketConnection(
                unix_socket_path, socket_timeout=socket_timeout)
        else:
            self.connection = XenBusConnection(xen_bus_path)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.connection.disconnect()

    # Private API.
    # ............

    def send(self, type, payload):
        # .. note:: `req_id` is allways 0 for now.
        self.connection.send(str(Packet(type, payload, req_id=0)))
        return self.connection.recv()

    def command(self, type, *args):
        packet = self.send(type, "".join(args))

        # According to ``xenstore.txt`` erroneous responses start with
        # a capital E and end with ``NULL``-byte.
        if not packet:
            raise RuntimeError(packet.payload[:-1])
        else:
            return packet.payload.rstrip("\x00")

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
        return self.command(Op.WRITE, path, value)

    @spec("<path>|")
    def mkdir(self, path):
        """Ensures that a given path exists, by creating it and any
        missing parents with empty values. If `path` or any parent
        already exist, its value is left unchanged.

        :param str path: path to directory to create.
        """
        return self.command(Op.MKDIR, path)

    @spec("<path>|")
    def rm(self, path):
        """Ensures that a given does not exist, by deleting it and all
        of its children. It is not an error if `path` doesn't exist, but
        it **is** an error if `path`'s immediate parent does not exist
        either.

        :param str path: path to directory to remove.
        """
        return self.command(Op.RM, path)

    @spec("<path>|")
    def directory(self, path):
        """Returns a list of names of the immediate children of `path`.
        The resulting children are each named as
        ``<path>/<child-leaf-name>``.

        :param str path: path to list.
        """
        return self.command(Op.DIRECTORY, path).split("\x00")

    @spec("<path>|")
    def get_perms(self, path):
        """Returns a list of permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param str path: path to get permissions for.
        """
        return self.command(Op.GET_PERMS, path).split("\x00")

    @spec("<path>|", "<perms>|+")
    def set_perms(self, path, perms):
        """Sets a access permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.

        :param str path: path to set permissions for.
        :param list perms: a list of permissions to set.
        """
        return self.command(Op.SET_PERMS, path, *perms)

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
        return self.command(Op.WATCH, wpath, token)

    @spec("<wpath>|", "<token>|")
    def unwatch(self, wpath, token):
        """Removes a previously added watch.

        :param str wpath: path to unwatch.
        :param str token: watch token, passed to :meth:`watch`.
        """
        return self.command(Op.UNWATCH, wpath, token)

    def watch_event(self):
        """Waits for any of the watched paths to generate an event,
        which is a ``(path, token)`` pair, where the first element
        is event path, i.e. the actual path that was modified and
        second element is a token, passed to the :meth:`watch`.
        """
        return Event(*self.command(Op.WATCH_EVENT).split("\x00"))

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
        }.get(self.command(Op.IS_DOMAIN_INTRODUCED, domid))

    @spec("<domid>|", "<mfn>|", "<eventchn>|")
    def introduce(self, domid, mfn, eventchn):
        """Tells ``xenstored`` to communicate with this domain.

        :param int domid: a real domain id, (``0`` is forbidden).
        :param long mfn: address of xenstore page in `domid`.
        :param int eventch: an unbound event chanel in `domid`.
        """
        return self.command(Op.INTRODUCE, domid, mfn, eventchn)

    @spec("<domid>|")
    def release(self, domid):
        """Manually requests ``xenstored`` to disconnect from the
        domain.

        :param int domid: domain to disconnect.

        .. note:: ``xenstored`` will in any case detect domain
                  destruction and disconnect by itself.

        .. todo:: make sure it's only executed from Dom0.
        """
        return self.command(Op.RELEASE, domid)

    @spec("<domid>|")
    def resume(self, domid):
        """Tells ``xenstored`` to clear its shutdown flag for a
        domain. This ensures that a subsequent shutdown will fire the
        appropriate watches.

        :param int domid: domain to resume.

        .. todo:: make sure it's only executed from Dom0.
        """
        return self.command(Op.RESUME, domid)

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
        return self.command(Op.SET_TARGET, domid, target)
