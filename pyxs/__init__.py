# -*- coding: utf-8 -*-
"""
    pyxs
    ~~~~

    Pure Python bindings for communicating with XenStore over Unix socket.
"""

import socket
import struct
from collections import namedtuple
from itertools import imap


#: Packet types, supported by XenStore.
PACKET_TYPES = (
    XS_DEBUG,
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
    XS_SET_TARGET
) = range(20)

XS_RESTRICT = 128

# ``XS_RESTRICT`` is somewhat an exception, so we need to add it
# manually -- we also convert ``PACKET_TYPES`` to a set() to get
# O(1) presence lookups.
PACKET_TYPES = set(PACKET_TYPES + [XS_RESTRICT])


class Packet(namedtuple("_Packet", "type req_id tx_id len payload")):
    """A single message to or from XenStore."""
    #: ``xsd_sockmsg`` struct format see ``xen/include/public/io/xs_wire.h``
    #: for details.
    _fmt = "IIII"

    #: ``xsd_sockmsg`` struct size.
    _fmt_size = struct.calcsize(_fmt)

    def __new__(cls, type, payload, req_id=None, tx_id=None):
        if type not in PACKET_TYPES:
            raise ValueError("Invalid packet type: {0}".format(type))

        # ``0`` transaction id means no transaction is running.
        if tx_id is None: tx_id = 0

        return super(Packet, cls).__new__(cls,
            type, req_id or 0, tx_id, len(payload), payload)

    @classmethod
    def from_string(cls, s):
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
        # Checking restrictions:

        # a) payload is limited to 4096 bytes.
        if len(payload) > 4096:
            raise ValueError("payload size exceeded: {0}".format(len(payload)))
        # b) xenstore values should normally be 7-bit ASCII text strings
        #    containing bytes 0x20..0x7f only.
        if any(c and (c > 0x7f or c < 0x20) for c in imap(ord, payload)):
            raise ValueError("payload contains invalid characters.")

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
        return self.send(XS_DEBUG, "\x00".join(map(bytes, args)))
