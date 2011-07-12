# -*- coding: utf-8 -*-
"""
    pyxs.client
    ~~~~~~~~~~~

    This module implements XenStore client, which uses Unix socket for
    communication.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""


import re
import socket

from . import Packet, Op
from .helpers import spec


class Client(object):

    def __init__(self, addr):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.connect(addr)

    # Private API.
    # ............

    def send(self, type, payload):
        # .. note:: `req_id` is allways 0 for now.
        self.socket.send(str(Packet(type, payload, 0)))

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

    def command(self, type, *args):
        packet = self.send(type, "\x00".join(args))

        # According to ``xenstore.txt`` erroneous responses start with
        # a capital E and end with ``NULL``-byte.
        if re.match(r"^E[A-Z]+\x00$", packet.payload):
            raise RuntimeError(packet.payload[:-1])

        return packet.payload.rstrip("\x00")

    # Public API.
    # ...........

    @spec("<path>|")
    def read(self, path):
        """Reads the octet string value at a given path."""
        return self.command(Op.READ, path + "\x00")

    @spec("<path>|", "<value|>")
    def write(self, path, value):
        """Write a value to a given path."""
        return self.command(Op.WRITE, path, value)

    @spec("<path>|")
    def mkdir(self, path):
        """Ensures that a given path exists, by creating it and any
        missing parents with empty values. If `path` or any parent
        already exist, its value is left unchanged.
        """
        return self.command(Op.MKDIR, path + "\x00")

    @spec("<path>|")
    def rm(self, path):
        """Ensures that a given does not exist, by deleting it and all
        of its children. It is not an error if `path` doesn't exist, but
        it **is** an error if `path`'s immediate parent does not exist
        either.
        """
        return self.command(Op.RM, path + "\x00")

    @spec("<path>|")
    def directory(self, path):
        """Returns a list of names of the immediate children of `path`.
        The resulting children are each named as
        ``<path>/<child-leaf-name>``.
        """
        return self.command(Op.DIRECTORY, path + "\x00").split("\x00")

    @spec("<path>|")
    def get_perms(self, path):
        """Returns a list of permissions for a given `path`, where each
        item is one of the following::

            w<domid>	write only
            r<domid>	read only
            b<domid>	both read and write
            n<domid>	no access
        """
        return self.command(Op.GET_PERMS, path + "\x00").split("\x00")
