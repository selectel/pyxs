# -*- coding: utf-8 -*-
"""
    pyxs
    ~~~~

    Pure Python bindings for communicating with XenStore.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
    :license: LGPL, see LICENSE for more details.
"""

__all__ = ["Router", "Client", "Monitor",
           "PyXSError", "ConnectionError", "UnexpectedPacket",
           "InvalidOperation", "InvalidPath", "InvalidPayload",
           "xs", "Error"]

from contextlib import contextmanager

from .client import Router, Client, Monitor
from .exceptions import PyXSError, ConnectionError, UnexpectedPacket, \
    InvalidOperation, InvalidPath, InvalidPayload
from ._compat import xs, Error


@contextmanager
def monitor(*args, **kwargs):
    """A simple shortcut for creating :class:`~pyxs.client.Monitor`
    instances. All arguments are forwared to :class:`~pyxs.client.Client`
    constructor.
    """
    with Client(*args, **kwargs) as c:
        with c.monitor() as m:
            yield m
