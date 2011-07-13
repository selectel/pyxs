# -*- coding: utf-8 -*-
"""
    pyxs._internal
    ~~~~~~~~~~~~~~

    A place for secret stuff, not available in the public API.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import unicode_literals

__all__ = ["Event", "Op", "Packet"]

import re
import struct
from collections import namedtuple

from .exceptions import InvalidOperation, InvalidPayload


#: Operations supported by XenStore.
Operations = Op = namedtuple("Operations", [
    "DEBUG",
    "DIRECTORY",
    "READ",
    "GET_PERMS",
    "WATCH",
    "UNWATCH",
    "TRANSACTION_START",
    "TRANSACTION_END",
    "INTRODUCE",
    "RELEASE",
    "GET_DOMAIN_PATH",
    "WRITE",
    "MKDIR",
    "RM",
    "SET_PERMS",
    "WATCH_EVENT",
    "ERROR",
    "IS_DOMAIN_INTRODUCED",
    "RESUME",
    "SET_TARGET",
    "RESTRICT"
])(*(range(20) + [128]))


Event = namedtuple("Event", "path token")


class Packet(namedtuple("_Packet", "op req_id tx_id len payload")):
    """A single message to or from XenStore.

    :param int op: an item from :data:`~pyxs.Op`, representing
                   operation, performed by this packet.
    :param bytes payload: packet payload, should be a valid ASCII-string
                          with characters between ``[0x20;0x7f]``.
    :param int req_id: request id -- hopefuly a **unique** identifier
                       for this packet.
    :param int tx_id: transaction id, defaults to ``0`` -- which means
                      no transaction is running.
    """
    #: ``xsd_sockmsg`` struct format see ``xen/include/public/io/xs_wire.h``
    #: for details.
    _fmt = b"IIII"

    def __new__(cls, op, payload, req_id, tx_id=None):
        if isinstance(payload, unicode):
            payload = payload.encode("utf-8")

        # Checking restrictions:
        # a) payload is limited to 4096 bytes.
        if len(payload) > 4096:
            raise InvalidPayload(payload)
        # b) operation requested is present in ``xsd_sockmsg_type``.
        if op not in Op:
            raise InvalidOperation(op)

        if tx_id is None: tx_id = 0

        return super(Packet, cls).__new__(cls,
            op, req_id or 0, tx_id, len(payload), payload)

    def __nonzero__(self):
        return not re.match(r"^E[A-Z]+\x00$", self.payload)

    @classmethod
    def from_string(cls, s):
        if isinstance(s, unicode):
            s = s.encode("utf-8")

        op, req_id, tx_id, l = map(int,
            struct.unpack(cls._fmt, s[:struct.calcsize(cls._fmt)]))
        return cls(op, s[-l:], req_id, tx_id)

    @classmethod
    def from_file(cls, f):
        op, req_id, tx_id, l = map(int, struct.unpack(cls._fmt, f.read(16)))
        return cls(op, f.read(l), req_id, tx_id)

    def __str__(self):
        # Note the ``[:-1]`` slice -- the actual payload is excluded.
        return struct.pack(self._fmt, *self[:-1]) + self.payload
