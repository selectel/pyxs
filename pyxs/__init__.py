# -*- coding: utf-8 -*-
"""
    pyxs
    ~~~~

    Pure Python bindings for communicating with XenStore. Currently two
    backend options are available:

    * over a Unix socket with :class:`~pyxs.client.UnixSocketConnection`;
    * over XenBus_ with :class:`~pyxs.client.XenBusConnection`.

    Which backend is used is determined by the arguments used for
    :class:`~pyxs.client.Client` initialization, for example the
    following code creates a :class:`~pyxs.client.Client` instance,
    working over a Unix socket:

    >>> Client(unix_socket_path="/var/run/xenstored/socket")
    <pyxs.client.Client object at 0xb74103cc>
    >>> Client()
    <pyxs.client.Client object at 0xb74109cc>

    Use ``xen_bus_path``, if initialize a :class:`~pyxs.client.Client`
    over XenBus_:

    >>> Client(xen_bus_path="/proc/xen/xenbus")
    <pyxs.client.Client object at 0xb7410d2c>

    .. _XenBus: http://wiki.xensource.com/xenwiki/XenBus

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from .client import Client
from .exceptions import ConnectionError, InvalidOperation, InvalidPath, \
    InvalidPayload, InvalidTerm

