# -*- coding: utf-8 -*-
"""
    pyxs.connection
    ~~~~~~~~~~~~~~~

    This module implements two connection backends for
    :class:`~pyxs.client.Client`.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
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
        if self.is_closed:
            status = "closed"
        elif self.is_active:
            status = "connected"
        else:
            status = "initial"

        return "{0}({1})".format(self.__class__.__name__, self.path, status)

    @property
    def is_active(self):
        return self.fd is not None

    @property
    def is_closed(self):
        return self.path is None

    def fileno(self):
        return self.fd

    def close(self, silent=True):
        """Disconnects from XenStore.

        :param bool silent: if ``True`` (default), any errors, raised
                            while closing the file descriptor are
                            suppressed.
        """
        if not self.is_active:
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
        if not self.is_active:
            raise ConnectionError("not connected")

        # Note the ``[:-1]`` slice -- the actual payload is excluded.
        data = packet._struct.pack(*packet[:-1]) + packet.payload

        try:
            writeall(self.fd, data)
        except OSError as e:
            if e.args[0] in [errno.ECONNRESET,
                             errno.ECONNABORTED,
                             errno.EPIPE]:
                self.close()

            raise ConnectionError("error while writing to {0!r}: {1}"
                                  .format(self.path, e.args))

    def recv(self):
        """Receives a packet from XenStore."""
        if not self.is_active:
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

            # XXX XenBus seems to handle ``os.read(fd, 0)`` incorrectly,
            # blocking unless any new data appears, so we have to check
            # size value, before reading.
            payload = b"" if not size else os.read(self.fd, size)
            return Packet(op, payload, rq_id, tx_id)


class UnixSocketConnection(FileDescriptorConnection):
    """XenStore connection through Unix domain socket.

    :param str path: path to XenStore unix domain socket, if not
                     provided explicitly is restored from process
                     environment -- similar to what ``libxs`` does.
    """
    def __init__(self, path=None):
        if path is None:
            path = (
                os.getenv("XENSTORED_PATH") or
                os.path.join(os.getenv("XENSTORED_RUNDIR",
                                       "/var/run/xenstored"), "socket")
            )

        self.path = path

    def connect(self):
        if self.is_active:
            return

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.path)
        except socket.error as e:
            raise ConnectionError("error connecting to {0!r}: {1}"
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

            if system == "Linux" and not os.access("/dev/xen/xenbus", os.R_OK):
                # See commit 9c89dc95201ffed5fead17b35754bf9440fdbdc0 in
                # http://xenbits.xen.org/gitweb/?p=xen.git for details on the
                # ``os.access`` check.
                path = "/proc/xen/xenbus"
            elif system == "NetBSD":
                path = "/kern/xen/xenbus"
            else:
                path = "/dev/xen/xenbus"

        self.path = path

    def connect(self):
        if self.is_active:
            return

        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except OSError as e:
            raise ConnectionError("error while opening {0!r}: {1}"
                                  .format(self.path, e.args))
