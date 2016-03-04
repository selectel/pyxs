# -*- coding: utf-8 -*-
"""
    pyxs._internal
    ~~~~~~~~~~~~~~

    A place for secret stuff, not available in the public API.

    :copyright: (c) 2011 by Selectel.
    :copyright: (c) 2016 by pyxs authors and contributors, see AUTHORS
                for more details.
    :license: LGPL, see LICENSE for more details.
"""

from __future__ import absolute_import

__all__ = ["NUL", "Event", "Op", "Packet", "next_rq_id"]

import struct
import sys
from collections import namedtuple

from .exceptions import InvalidOperation, InvalidPayload

#: NUL byte.
NUL = b"\x00"

#: Operations supported by XenStore.
Operations = Op = namedtuple("Operations", [
    "DEBUG",                 # 0
    "DIRECTORY",             # 1
    "READ",                  # 2
    "GET_PERMS",             # 3
    "WATCH",                 # 4
    "UNWATCH",               # 5
    "TRANSACTION_START",     # 6
    "TRANSACTION_END",       # 7
    "INTRODUCE",             # 8
    "RELEASE",               # 9
    "GET_DOMAIN_PATH",       # 10
    "WRITE",                 # 11
    "MKDIR",                 # 12
    "RM",                    # 13
    "SET_PERMS",             # 14
    "WATCH_EVENT",           # 15
    "ERROR",                 # 16
    "IS_DOMAIN_INTRODUCED",  # 17
    "RESUME",                # 18
    "SET_TARGET",            # 19
    "RESTRICT"               # 128
])(*(list(range(20)) + [128]))


Event = namedtuple("Event", "path token")


class Packet(namedtuple("_Packet", "op rq_id tx_id size payload")):
    """A message to or from XenStore.

    :param int op: an item from :data:`~pyxs._internal.Op`, representing
                   operation, performed by this packet.
    :param bytes payload: packet payload, should be a valid ASCII-string
                          with characters between ``[0x20; 0x7f]``.
    :param int rq_id: request id -- hopefuly a **unique** identifier
                      for this packet, XenStore simply echoes this value
                      back in reponse.
    :param int tx_id: transaction id, defaults to ``0`` , which means
                      no transaction is running.

    .. versionchanged:: 0.4.0

       ``rq_id`` no longer defaults to ``0`` and should be provided
       explicitly.
    """
    #: ``xsd_sockmsg`` struct see ``xen/include/public/io/xs_wire.h``
    #: for details.
    _struct = struct.Struct(b"IIII")

    def __new__(cls, op, payload, rq_id, tx_id=None):
        # Checking restrictions:
        # a) payload is limited to 4096 bytes.
        if len(payload) > 4096:
            raise InvalidPayload(payload)
        # b) operation requested is present in ``xsd_sockmsg_type``.
        if op not in Op:
            raise InvalidOperation(op)

        return super(Packet, cls).__new__(
            cls, op, rq_id, tx_id or 0, len(payload), payload)


_rq_id = -1

def next_rq_id():
    """Returns the next available request id."""
    # XXX we don't need a mutex because of the GIL.
    global _rq_id
    _rq_id += 1
    _rq_id %= sys.maxsize
    return _rq_id
