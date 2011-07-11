# -*- coding: utf-8 -*-
"""
    pyxs
    ~~~~

    Pure Python bindings for communicating with XenStore over Unix socket.
"""

import socket
import struct
from collections import namedtuple


#: Packet types, supported by XenStore.
(XS_DEBUG,
 XS_DIRECTORY,
 XS_READ,
 XS_GET_PERMS,
 XS_WATCH,
 XS_UNWATCH,
 XS_TRANSACTION_START,
 XS_TRANSACTION_END,
 XS_INTRODUCE,
 XS_RELEASE,
 XS_GET_DOMAIN_PATH,
 XS_WRITE,
 XS_MKDIR,
 XS_RM,
 XS_SET_PERMS,
 XS_WATCH_EVENT,
 XS_ERROR,
 XS_IS_DOMAIN_INTRODUCED,
 XS_RESUME,
 XS_SET_TARGET) = xrange(20)

XS_RESTRICT = 128


class Header(namedtuple("_Header", "type req_id tx_id len")):
    #: ``xsd_sockmsg`` struct format see ``xen/include/public/io/xs_wire.h``
    #: for details.
    _fmt = "IIII"

    #: ``xsd_sockmsg`` struct size.
    _fmt_size = struct.calcsize(_fmt)

    @classmethod
    def from_string(cls, s):
        return cls(*map(int, struct.unpack(cls._fmt, s[:cls._fmt_size])))

    def __str__(self):
        return struct.pack(self._fmt, *self)


class Packet(namedtuple("_Packet", "header payload")):
    def __new__(cls, type, payload, req_id=None, tx_id=None):
        header = Header(type, req_id or 0, tx_id or 0, len(payload))
        return super(Packet, cls).__new__(cls, header, payload)

    @classmethod
    def from_string(cls, s):
        header = Header.from_string(s)
        return cls(header, s[-header.len:])

    def __str__(self):
        return str(self.header) + self.payload


class Connection(object):
    def __init__(self, addr):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(addr)

    def send(self, type, payload):
        self.socket.send(str(Packet(type, payload)))

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
