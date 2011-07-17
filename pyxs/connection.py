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

from .exceptions import ConnectionError
from .helpers import writeall
from ._internal import Packet


class FileDescriptorConnection(object):
    """Abstract XenStore connection, using an fd for I/O operations.

    Subclasses are expected to define :meth:`connect()` and set
    :attr:`fd` and :attr:`path` attributes, where `path` is a human
    readable path to the object, `fd` points to.
    """
    fd = path = None

    def __init__(self):
        raise NotImplemented("__init__() should be overriden by subclasses.")

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

        try:
            writeall(self.fd, str(packet))
        except OSError as e:
            if e.args[0] is errno.EPIPE:
                self.disconnect()

            raise ConnectionError("Error while writing to {0!r}: {1}"
                                  .format(self.path, e.args))

    def recv(self):
        """Recieves a packet from XenStore."""
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
