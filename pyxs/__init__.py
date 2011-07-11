# -*- coding: utf-8 -*-
"""
    pyxenstore
    ~~~~~~~~~~

    Pure Python bindings for communicating with XenStore over Unix socket.
"""

import struct
from collections import namedtuple


class Header(namedtuple("_Header", "type req_id tx_id len")):
    fmt = "IIII"
    fmt_size = struct.calcsize(fmt)

    def __str__(self):
        return struct.pack(self.fmt, *self)

    @classmethod
    def from_string(cls, s):
        return cls(*map(int, struct.unpack(cls.fmt, s[:cls.fmt_size])))


class Packet(namedtuple("_Packet", "header payload")):
    def __init__(self, type, payload, req_id=None, tx_id=None):
        header = Header(type, req_id, tx_id, len(payload))
        super(Packet, self).__init__(header, payload)

    def __str__(self):
        return str(self.header) + self.payload

    @classmethod
    def from_string(cls, s):
        header = Header.from_string(s)
        return cls(header, s[-header.len:])
