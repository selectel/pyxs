# -*- coding: utf-8 -*-
"""
    pyxs._compat
    ~~~~~~~~~~~~

    This module implements compatibility interface for scripts,
    using ``xen.lowlevel.xs``.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

__all__ = ["xs", "Error"]

from .client import Client
from .exceptions import PyXSError as Error


class xs(Client):
    def close(self):
        self.connection.disconnect()

    def get_permissions(self, tx_id, path):
        self.tx_id = int(tx_id)
        super(Client, self).get_perms(path)

    def set_permissions(self, tx_id, path, perms):
        self.tx_id = int(tx_id)
        super(Client, self).set_perms(path, perms)

    def ls(self, path):
        return super(Client, self).directory(path) or None

    def rm(self, tx_id, path):
        self.tx_id = int(tx_id)
        super(Client, self).rm(path)

    def read(self, tx_id, path):
        self.tx_id = int(tx_id)
        return super(Client, self).read(path)

    def write(self, tx_id, path, value):
        self.tx_id = int(tx_id)
        return super(Client, self).write(path, value)

    def introduce_domain(self, *args):
        try:
            super(Client, self).introduce(*args)
        except ValueError as e:
            raise PyXSError(e)

    release_domain = Client.release
    resume_domain = Client.resume

    def transaction_end(self, abort=0):
        try:
            super(Client, self).transaction_end(commit=not abort)
        except PyXSError as e:
            if len(e.args) is 1:
                return False
            raise
        else:
            return True

    read_watch = Client.wait
