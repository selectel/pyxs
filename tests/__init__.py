# -*- coding: utf-8 -*-

import os

import pytest

from pyxs import Client

# XXX we don't always need 'SU'.
_virtualized = not os.path.exists('/dev/xen') or not Client.SU

virtualized = pytest.mark.skipif(_virtualized, reason="not virtualized")
