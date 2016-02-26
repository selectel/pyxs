# -*- coding: utf-8 -*-
"""
    pyxs
    ~~~~

    Pure Python bindings for communicating with XenStore. Currently two
    backend options are available:

    * over a Unix socket with :class:`~pyxs.connection.UnixSocketConnection`;
    * over XenBus_ with :class:`~pyxs.connection.XenBusConnection`.

    Which backend is used is determined by the arguments used for
    :class:`~pyxs.client.Client` initialization, for example the
    following code creates a :class:`~pyxs.client.Client` instance,
    working over a Unix socket:

    >>> Client(unix_socket_path="/var/run/xenstored/socket")
    <pyxs.client.Client object at 0xb74103cc>
    >>> Client()
    <pyxs.client.Client object at 0xb74109cc>

    Use ``xen_bus_path`` argument to initialize a
    :class:`~pyxs.client.Client`, communicating with XenStore over
    XenBus_:

    >>> Client(xen_bus_path="/proc/xen/xenbus")
    <pyxs.client.Client object at 0xb7410d2c>

    .. _XenBus: http://wiki.xensource.com/xenwiki/XenBus

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
    """A simple shortcut for creating :class:`Monitor` instances.
    All arguments are forwared to :class:`Client` constructor.
    """
    with Client(*args, **kwargs) as c:
        with c.monitor() as m:
            yield m
