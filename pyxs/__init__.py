# -*- coding: utf-8 -*-
"""
    pyxs
    ~~~~

    Pure Python bindings for communicating with XenStore over Unix socket.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import absolute_import, print_function, unicode_literals

import socket
import struct
from collections import namedtuple
from itertools import imap

from .exceptions import InvalidOperation, InvalidPayload


#: Operations supported by XenStore.
Op = namedtuple("Operation", [
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

    #: ``xsd_sockmsg`` struct size.
    _fmt_size = struct.calcsize(_fmt)

    def __new__(cls, op, payload, req_id, tx_id=None):
        if isinstance(payload, unicode):
            payload = payload.encode("utf-8")

        # Checking restrictions:
        # a) payload is limited to 4096 bytes.
        if len(payload) > 4096:
            raise InvalidPayload(payload)
        # b) xenstore values should normally be 7-bit ASCII text strings
        #    containing bytes 0x20..0x7f only.
        if any(c and (c > 0x7f or c < 0x20) for c in imap(ord, payload)):
            raise InvalidPayload(payload)
        # c) operation requested is present in ``xsd_sockmsg_type``.
        if op not in Op:
            raise InvalidOperation(op)

        if tx_id is None: tx_id = 0

        return super(Packet, cls).__new__(cls,
            op, req_id or 0, tx_id, len(payload), payload)

    @classmethod
    def from_string(cls, s):
        if isinstance(s, unicode):
            s = s.encode("utf-8")

        type, req_id, tx_id, l = map(int, struct.unpack(cls._fmt,
                                                        s[:cls._fmt_size]))
        return cls(type, s[-l:], req_id, tx_id)

    def __str__(self):
        # Note the ``[:-1]`` slice -- the actual payload is excluded.
        return struct.pack(self._fmt, *self[:-1]) + self.payload


class Connection(object):
    """XenStore connection object.

    The following conventions are used to desribe method arguments:

    =======  ============================================================
    Symbol   Semantics
    =======  ============================================================
    ``|``    A ``NULL`` (zero) byte.
    <foo>    A string guaranteed not to contain any ``NULL`` bytes.
    <foo|>   Binary data (which may contain zero or more ``NULL`` bytes).
    <foo>|*  Zero or more strings each followed by a trailing ``NULL``.
    <foo>|+  One or more strings each followed by a trailing ``NULL``.
    ?        Reserved value (may not contain ``NULL`` bytes).
    ??       Reserved value (may contain ``NULL`` bytes).
    =======  ============================================================

    .. note::

       According to ``docs/misc/xenstore.txt`` in the current
       implementation reserved values are just empty strings. So for
       example ``"\\x00\\x00\\x00"`` is a valid ``??`` symbol.

    Here're some examples:

    >>> c = Connection("/var/run/xenstored/socket")
    >>> c.debug("print", "hello world!", "\x00")
    _Packet(type=0, req_id=0, tx_id=0, len=3, payload='OK\x00')
    """

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

    def debug(self, *args):
        """A simple echo call.

        **Syntax**::

          "print"|<string>|??           sends <string> to debug log
          "print"|<thing-with-no-null>  EINVAL
          "check"|??                    check xenstored internals
          <anything-else|>              no-op (future extension)
        """
        return self.send(Op.DEBUG, "\x00".join(map(bytes, args)))
