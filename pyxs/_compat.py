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

import errno

from .client import Client
from .exceptions import PyXSError as Error


class xs:
    """XenStore client with a backward compatible interface, useful for
    switching from ``xen.lowlevel.xs``.
    """
    def __init__(self):
        self.client = Client()
        self.client.connect()
        self.monitor = self.client.monitor()
        self.token_aliases = {}

    def close(self):
        self.client.close()

    def get_permissions(self, tx_id, path):
        self.client.tx_id = int(tx_id or 0)
        self.client.get_perms(path)

    def set_permissions(self, tx_id, path, perms):
        self.client.tx_id = int(tx_id or 0)
        self.client.set_perms(path, perms)

    def ls(self, tx_id, path):
        self.client.tx_id = int(tx_id or 0)
        try:
            return self.client.list(path)
        except Error as e:
            if e.args[0] == errno.ENOENT:
                return

            raise

    def mkdir(self, tx_id, path):
        self.client.tx_id = int(tx_id or 0)
        self.client.mkdir(path)

    def rm(self, tx_id, path):
        self.client.tx_id = int(tx_id or 0)
        self.client.delete(path)

    def read(self, tx_id, path):
        self.client.tx_id = int(tx_id or 0)
        return self.client.read(path)

    def write(self, tx_id, path, value):
        self.client.tx_id = int(tx_id or 0)
        return self.client.write(path, value)

    def get_domain_path(self, domid):
        return self.client.get_domain_path(domid)

    def introduce_domain(self, domid, mfn, eventchn):
        self.client.introduce_domain(domid, mfn, eventchn)

    def release_domain(self, domid):
        self.client.release_domain(domid)

    def resume_domain(self, domid):
        self.client.resume_domain(domid)

    def set_target(self, domid, target):
        self.client.set_target(domid, target)

    def transaction_start(self):
        return str(self.client.transaction())

    def transaction_end(self, tx_id, abort=0):
        self.client.tx_id = int(tx_id or 0)
        if abort:
            self.client.rollback()
        else:
            try:
                self.client.commit()
            except Error as e:
                if e.args[0] == errno.EAGAIN:
                    return False

                raise

        return True

    def watch(self, path, token):
        # Even though ``xs.watch`` docstring states that token should be
        # a string, it in fact can be any Python object; and unfortunately
        # some scripts rely on that behaviour.
        stub = bytes(id(token))
        self.token_aliases[stub] = token
        return self.monitor.watch(path, stub)

    def unwatch(self, path, token):
        stub = bytes(id(token))
        return self.monitor.unwatch(path, stub)

    def read_watch(self):
        event = next(self.monitor.wait())
        return event._replace(token=self.token_aliases[event.token])
