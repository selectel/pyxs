# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pytest

from pyxs.connection import _XenBusTransport, _UnixSocketTransport
from pyxs.exceptions import ConnectionError


@pytest.mark.parametrize("_transport", [
    _XenBusTransport, _UnixSocketTransport
])
def test_transport_init_failed(tmpdir, _transport):
    with pytest.raises(ConnectionError):
        _transport(str(tmpdir.join("unexisting")))
