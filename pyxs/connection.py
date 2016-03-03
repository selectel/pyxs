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

from .exceptions import ConnectionError
from .helpers import writeall, readall
from ._internal import Packet


class FileDescriptorConnection(object):
    """Abstract XenStore connection which uses an fd for I/O operations.

    Subclasses are expected to define :meth:`connect()` and set
    :attr:`fd` and :attr:`path` attributes, where `path` is a human
    readable path to the object, `fd` points to.
    """
    fd = path = None

    def __init__(self):
        raise NotImplementedError(
            "__init__() should be overridden by subclasses.")

    def __repr__(self):
        return "{0}({1!r})".format(self.__class__.__name__, self.path)

    @property
    def is_connected(self):
        return self.fd is not None

    def fileno(self):
        return self.fd

    def close(self, silent=True):
        """Disconnects from XenStore.

        :param bool silent: if ``True`` (default), any errors, raised
                            while closing the file descriptor are
                            suppressed.
        """
        if not self.is_connected:
            return

        try:
            os.close(self.fd)
        except OSError as e:
            if not silent:
                raise ConnectionError(e.args)
        finally:
            self.fd = self.path = None

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
            writeall(self.fd, header)
            writeall(self.fd, packet.payload)
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
            header = readall(self.fd, Packet._struct.size)
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
            payload = b"" if not size else readall(self.fd, size)
            return Packet(op, payload, rq_id, tx_id)


def _get_unix_socket_path():
    """Returns default path to ``xenstored`` Unix domain socket."""
    return (os.getenv("XENSTORED_PATH") or
            os.path.join(os.getenv("XENSTORED_RUNDIR",
                                   "/var/run/xenstored"), "socket"))


class UnixSocketConnection(FileDescriptorConnection):
    """XenStore connection through Unix domain socket.

    :param str path: path to XenStore unix domain socket, if not
                     provided explicitly is restored from process
                     environment -- similar to what ``libxs`` does.
    """
    def __init__(self, path=None):
        self.path = path or _get_unix_socket_path()

    def connect(self):
        if self.is_connected:
            return

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.path)
        except socket.error as e:
            raise ConnectionError("error connecting to {0!r}: {1}"
                                  .format(self.path, e.args))
        else:
            self.fd = os.dup(sock.fileno())


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


class XenBusConnection(FileDescriptorConnection):
    """XenStore connection through XenBus.

    :param str path: path to XenBus. A predefined OS-specific
                     constant is used, if a value isn't
                     provided explicitly.
    """
    def __init__(self, path=None):
        self.path = path or _get_xenbus_path()

    def connect(self):
        if self.is_connected:
            return

        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except OSError as e:
            raise ConnectionError("error while opening {0!r}: {1}"
                                  .format(self.path, e.args))
