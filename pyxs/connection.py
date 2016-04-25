# -*- coding: utf-8 -*-
"""
    pyxs.connection
    ~~~~~~~~~~~~~~~

    This module implements two connection backends for
    :class:`~pyxs.client.Client`.

    :copyright: (c) 2011 by Selectel.
    :copyright: (c) 2016 by pyxs authors and contributors, see AUTHORS
                for more details.
    :license: LGPL, see LICENSE for more details.
"""

from __future__ import absolute_import

__all__ = ["UnixSocketConnection", "XenBusConnection"]

import errno
import os
import platform
import socket
import sys

from .exceptions import ConnectionError
from ._internal import Packet


class PacketConnection(object):
    """A connection which operates in terms of XenStore packets.

    Subclasses are expected to define :meth:`create_transport` and set
    :attr:`path` attribute.
    """
    path = transport = None

    def __repr__(self):
        return "{0}({1!r})".format(self.__class__.__name__, self.path)

    @property
    def is_connected(self):
        return self.transport is not None

    def fileno(self):
        return self.transport.fileno()

    def connect(self):
        """Connects to XenStore."""
        if self.is_connected:
            return

        self.transport = self.create_transport()

    def close(self, silent=True):
        """Disconnects from XenStore.

        :param bool silent: if ``True`` (default), any errors raised
                            while closing the file descriptor are
                            suppressed.
        """
        if not self.is_connected:
            return

        try:
            self.transport.close()
        except OSError as e:
            if not silent:
                raise ConnectionError(e.args)
        finally:
            self.transport = None

    def send(self, packet):
        """Sends a given packet to XenStore.

        :param pyxs._internal.Packet packet: a packet to send, is
            expected to be validated, since no checks are done at
            that point.
        """
        if not self.is_connected:
            raise ConnectionError("not connected")

        header = Packet._struct.pack(packet.op, packet.rq_id,
                                     packet.tx_id, packet.size)
        try:
            self.transport.send(header)
            self.transport.send(packet.payload)
        except OSError as e:
            if e.args[0] in [errno.ECONNRESET,
                             errno.ECONNABORTED,
                             errno.EPIPE]:
                self.close()

            raise ConnectionError("error while writing to {0!r}: {1}"
                                  .format(self.path, e.args))

    def recv(self):
        """Receives a packet from XenStore."""
        if not self.is_connected:
            raise ConnectionError("not connected")

        try:
            header = self.transport.recv(Packet._struct.size)
        except OSError as e:
            if e.args[0] in [errno.ECONNRESET,
                             errno.ECONNABORTED,
                             errno.EPIPE]:
                self.close()

            raise ConnectionError("error while reading from {0!r}: {1}"
                                  .format(self.path, e.args))
        else:
            op, rq_id, tx_id, size = Packet._struct.unpack(header)

            # On Linux XenBus blocks on ``os.read(fd, 0)``, so we have
            # to check the size before reading. See
            # http://lists.xen.org/archives/html/xen-devel/2016-03/msg00229
            # for discussion.
            payload = b"" if not size else self.transport.recv(size)
            return Packet(op, payload, rq_id, tx_id)


def _get_unix_socket_path():
    """Returns default path to ``xenstored`` Unix domain socket."""
    return (os.getenv("XENSTORED_PATH") or
            os.path.join(os.getenv("XENSTORED_RUNDIR",
                                   "/var/run/xenstored"), "socket"))


class _UnixSocketTransport(object):
    def __init__(self, path):
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(path)
        except socket.error as e:
            raise ConnectionError("error connecting to {0!r}: {1}"
                                  .format(path, e.args))

    def fileno(self):
        return self.sock.fileno()

    if sys.version_info[:2] < (2, 7):
        def recv(self, size):
            chunks = []
            while size:
                chunks.append(self.sock.recv(size))
                size -= len(chunks[-1])
            return b"".join(chunks)
    else:
        def recv(self, size):
            view = memoryview(bytearray(size))
            while size:
                received = self.sock.recv_into(view[-size:])
                if not received:
                    raise socket.error(errno.ECONNRESET)

                size -= received
            return view.tobytes()

    def send(self, data):
        self.sock.sendall(data)

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()


class UnixSocketConnection(PacketConnection):
    """XenStore connection through Unix domain socket.

    :param str path: path to XenStore unix domain socket, if not
                     provided explicitly is restored from process
                     environment -- similar to what ``libxs`` does.
    """

    def __init__(self, path=None):
        self.path = path or _get_unix_socket_path()

    def create_transport(self):
        return _UnixSocketTransport(self.path)


def _get_xenbus_path():
    """Returns OS-specific path to XenBus."""
    system = platform.system()
    if system == "Linux" and not os.access("/dev/xen/xenbus", os.R_OK):
        # See commit 9c89dc95201ffed5fead17b35754bf9440fdbdc0 in
        # http://xenbits.xen.org/gitweb/?p=xen.git for details on the
        # ``os.access`` check.
        return "/proc/xen/xenbus"
    elif system == "NetBSD":
        return "/kern/xen/xenbus"
    else:
        return "/dev/xen/xenbus"


class _XenBusTransport(object):
    def __init__(self, path):
        try:
            self.fd = os.open(path, os.O_RDWR)
        except OSError as e:
            raise ConnectionError("error while opening {0!r}: {1}"
                                  .format(path, e.args))

    def fileno(self):
        return self.fd

    def recv(self, size):
        chunks = []
        while size:
            read = os.read(self.fd, size)
            if not read:
                raise OSError(errno.ECONNRESET)

            chunks.append(read)
            size -= len(read)
        return b"".join(chunks)

    if sys.version_info[:2] < (2, 7):
        def send(self, data):
            size = len(data)
            while size:
                size -= os.write(self.fd, data[-size:])
    else:
        def send(self, data):
            size = len(data)
            view = memoryview(data)
            while size:
                size -= os.write(self.fd, view[-size:])

    def close(self):
        return os.close(self.fd)


class XenBusConnection(PacketConnection):
    """XenStore connection through XenBus.

    :param str path: path to XenBus. A predefined OS-specific
                     constant is used, if a value isn't
                     provided explicitly.
    """
    def __init__(self, path=None):
        self.path = path or _get_xenbus_path()

    def create_transport(self):
        return _XenBusTransport(self.path)
