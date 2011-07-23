# -*- coding: utf-8 -*-
"""
    pyxs.connection
    ~~~~~~~~~~~~~~~

    This module implements two connection backends for
    :class:`~pyxs.client.Client`.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import absolute_import, unicode_literals

__all__ = ["UnixSocketConnection", "XenBusConnection"]

import errno
import os
import platform
import socket
import sys

if sys.version_info[0] is not 3:
    bytes, str = str, unicode

from .exceptions import ConnectionError
from .helpers import writeall, readall
from ._internal import Packet


class FileDescriptorConnection(object):
    """Abstract XenStore connection, using an fd for I/O operations.

    Subclasses are expected to define :meth:`connect()` and set
    :attr:`fd` and :attr:`path` attributes, where `path` is a human
    readable path to the object, `fd` points to.
    """
    fd = path = None

    def __init__(self):
        raise NotImplemented("__init__() should be overridden by subclasses.")

    def disconnect(self, silent=True):
        """Disconnects from XenStore.

        :param bool silent: if ``True`` (default), any errors, raised
                            while closing the file descriptor are
                            suppressed.
        """
        if self.fd is None:
            return

        try:
            os.close(self.fd)
        except OSError as e:
            if not silent:
                raise ConnectionError(e.args)
        finally:
            self.fd = None

    def send(self, packet):
        """Sends a given packet to XenStore.

        :param pyxs._internal.Packet packet: a packet to send, is
            expected to be validated, since no checks are done at
            that point.
        """
        if not self.fd:
            self.connect()

        # Note the ``[:-1]`` slice -- the actual payload is excluded.
        data = (packet._struct.pack(*packet[:-1]) +
                packet.payload.encode("utf-8"))

        try:
            writeall(self.fd, data)
        except OSError as e:
            if e.args[0] in [errno.ECONNRESET,
                             errno.ECONNABORTED,
                             errno.EPIPE]:
                self.disconnect()

            raise ConnectionError("Error while writing to {0!r}: {1}"
                                  .format(self.path, e.args))

    def recv(self):
        """Receives a packet from XenStore."""
        try:
            header = readall(self.fd, Packet._struct.size)
        except OSError as e:
            if e.args[0] in [errno.ECONNRESET,
                             errno.ECONNABORTED,
                             errno.EPIPE]:
                self.disconnect()

            raise ConnectionError("Error while reading from {0!r}: {1}"
                                  .format(self.path, e.args))
        else:
            op, rq_id, tx_id, size = Packet._struct.unpack(header)

            # XXX XenBus seems to handle ``os.read(fd, 0)`` incorrectly,
            # blocking unless any new data appears, so we have to check
            # size value, before reading.
            payload = ("" if size is 0 else
                       os.read(self.fd, size).decode("utf-8"))

            return Packet(op, payload, rq_id, tx_id)


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
        self.socket_timeout = socket_timeout

    def __copy__(self):
        return self.__class__(self.path, self.socket_timeout)

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
            self.fd = os.dup(sock.fileno())

class XenBusConnection(FileDescriptorConnection):
    """XenStore connection through XenBus.

    :param str path: path to XenBus block device; a predefined
                     OS-specific constant is used, if a value isn't
                     provided explicitly.
    """
    def __init__(self, path=None):
        if path is None:
            # .. note:: it looks like OCaml-powered ``xenstored``
            # simply ignores the possibility of being launched on a
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

    def __copy__(self):
        return self.__class__(self.path)

    def connect(self):
        if self.fd:
            return

        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except OSError as e:
            raise ConnectionError("Error while opening {0!r}: {1}"
                                  .format(self.path, e.args))
