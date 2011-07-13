# -*- coding: utf-8 -*-
"""
    pyxs.client
    ~~~~~~~~~~~

    This module implements XenStore client, which uses Unix socket for
    communication.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import absolute_import

__all__ = ["Client"]

import errno
import re
import socket

from ._internal import Event, Packet, Op
from .helpers import spec
from .exceptions import ConnectionError


class UnixSocketConnection(object):
    def __init__(self, path="", socket_timeout=None):
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

    def send(self, data):
        if not self.socket:
            self.connect()

        try:
            return self.socket.send(data)
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
            return "".join(chunks)


class Client(object):
    """XenStore client -- <useful comment>.

    :param str unix_socket_path: path to XenStore Unix domain socket,
                                 usually something like
                                 ``/var/run/xenstored/socket``.
    :param float socket_timeout: see :func:`socket.settimeout` for
                                 details.
    """
    def __init__(self, unix_socket_path, socket_timeout=None):
        self.connection = UnixSocketConnection(unix_socket_path,
                                               socket_timeout=socket_timeout)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if not any(exc_info):
            self.connection.disconnect()

    # Private API.
    # ............

    def send(self, type, payload):
        # .. note:: `req_id` is allways 0 for now.
        self.connection.send(str(Packet(type, payload, req_id=0)))
        return Packet.from_string("".join(self.connection.recv()))

    def command(self, type, *args):
        packet = self.send(type, "".join(args))

        # According to ``xenstore.txt`` erroneous responses start with
        # a capital E and end with ``NULL``-byte.
        if re.match(r"^E[A-Z]+\x00$", packet.payload):
            raise RuntimeError(packet.payload[:-1])

        return packet.payload.rstrip("\x00")

    # Public API.
    # ...........

    @spec("<path>|")
    def read(self, path):
        """Reads the octet string value at a given path."""
        return self.command(Op.READ, path)

    @spec("<path>|", "<value|>")
    def write(self, path, value):
        """Write a value to a given path."""
        return self.command(Op.WRITE, path, value)

    @spec("<path>|")
    def mkdir(self, path):
        """Ensures that a given path exists, by creating it and any
        missing parents with empty values. If `path` or any parent
        already exist, its value is left unchanged.
        """
        return self.command(Op.MKDIR, path)

    @spec("<path>|")
    def rm(self, path):
        """Ensures that a given does not exist, by deleting it and all
        of its children. It is not an error if `path` doesn't exist, but
        it **is** an error if `path`'s immediate parent does not exist
        either.
        """
        return self.command(Op.RM, path)

    @spec("<path>|")
    def directory(self, path):
        """Returns a list of names of the immediate children of `path`.
        The resulting children are each named as
        ``<path>/<child-leaf-name>``.
        """
        return self.command(Op.DIRECTORY, path).split("\x00")

    @spec("<path>|")
    def get_perms(self, path):
        """Returns a list of permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.
        """
        return self.command(Op.GET_PERMS, path).split("\x00")

    @spec("<path>|", "<perms>|+")
    def set_perms(self, path, perms):
        """Sets a access permissions for a given `path`, see
        :exc:`~pyxs.exceptions.InvalidPermission` for details on
        permission format.
        """
        return self.command(Op.SET_PERMS, path, *perms)

    @spec("<wpath>|", "<token>|")
    def watch(self, wpath, token):
        """Adds a watch.

        When a `path` is modified (including path creation, removal,
        contents change or permissions change) this generates an event
        on the changed `path`. Changes made in transactions cause an
        event only if and when committed.
        """
        return self.command(Op.WATCH, wpath, token)

    @spec("<wpath>|", "<token>|")
    def unwatch(self, wpath, token):
        """Removes a previously added watch."""
        return self.command(Op.UNWATCH, wpath, token)

    def watch_event(self):
        """Waits for any of the watched paths to generate an event,
        which is a pair, where the first element is event path, i.e.
        the actual path that was modified and second element is a
        token, passed to the :meth:`watch` command.
        """
        return Event(*self.command(Op.WATCH_EVENT).split("\x00"))

    @spec("<domid>|")
    def get_domain_path(self, domid):
        """Returns the domain's base path, as is used for relative
        transactions: ex: ``"/local/domain/<domid>"``. If a given
        `domid` doesn't exists the answer is undefined.
        """
        return self.command(Op.GET_DOMAIN_PATH, domid)

    @spec("<domid>|")
    def is_domain_introduced(self, domid):
        """Returns ``True` if ``xenstored`` is in communication with
        the domain; that is when `INTRODUCE` for the domain has not
        yet been followed by domain destruction or explicit
        `RELEASE`; and ``False`` otherwise.
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

        .. note:: ``xenstored`` will in any case detect domain
                  destruction and disconnect by itself.
        """
        return self.command(Op.RELEASE, domid)

    @spec("<domid>|")
    def resume(self, domid):
        """Tells ``xenstored`` to clear its shutdown flag for a
        domain. This ensures that a subsequent shutdown will fire the
        appropriate watches.
        """
        return self.command(Op.RESUME, domid)

    @spec("<domid>|", "<tdomid>|")
    def set_target(self, domid, target):
        """Tells ``xenstored`` that a domain is tartetting another one,
        so it should let it tinker with it. This grants domain `domid`
        full access to paths owned by `target`. Domain `domid` also
        inherits all permissions granted to `target` on all other
        paths.
        """
        return self.command(Op.SET_TARGET, domid, target)
