# -*- coding: utf-8 -*-
"""
    pyxs._compat
    ~~~~~~~~~~~~

    This module implements compatibility interface for scripts,
    using ``xen.lowlevel.xs``.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
    :license: LGPL, see LICENSE for more details.
"""

__all__ = ["xs", "Error"]

from .client import Client
from .exceptions import PyXSError as Error


class xs(Client):
    """XenStore client with a backward compatible interface, useful for
    switching from ``xen.lowlevel.xs``.
    """
    watches = {}

    def close(self):
        self.connection.disconnect(silent=False)

    def execute_command(self, op, *args, **kwargs):
        try:
            return super(xs, self).execute_command(op, *args, **kwargs)
        except ValueError as e:
            raise Error(e)

    def get_permissions(self, tx_id, path):
        self.tx_id = int(tx_id or 0)
        super(xs, self).get_permissions(path)

    def set_permissions(self, tx_id, path, perms):
        self.tx_id = int(tx_id or 0)
        super(xs, self).set_permissions(path, perms)

    def ls(self, path):
        return super(xs, self).ls(path) or None

    def rm(self, tx_id, path):
        self.tx_id = int(tx_id or 0)
        super(xs, self).rm(path)

    def read(self, tx_id, path):
        self.tx_id = int(tx_id or 0)
        return super(xs, self).read(path)

    def write(self, tx_id, path, value):
        self.tx_id = int(tx_id or 0)
        return super(xs, self).write(path, value)

    def introduce_domain(self, *args):
        try:
            super(xs, self).introduce_domain(*args)
        except ValueError as e:
            raise Error(e)

    def transaction_end(self, abort=0):
        try:
            super(xs, self).transaction_end(commit=not abort)
        except Error as e:
            if len(e.args) is 1:
                return False
            raise
        else:
            return True

    def monitor(self):
        return Monitor(connection=self.connection)

    def watch(self, path, token):
        # Even though ``xs.watch`` docstring states that token should be
        # a string, it in fact can be any Python object; and unfortunately
        # some scripts rely on that behaviour.
        stub = str(id(token))
        self.watches[stub] = token
        return self.monitor().watch(path, stub)

    def unwatch(self, path, token):
        stub = str(id(token))
        self.watches.pop(stub, None)
        return self.monitor().unwatch(path, stub)

    def read_watch(self):
        event = self.monitor().wait()
        return event._replace(token=self.watches[event.token])
