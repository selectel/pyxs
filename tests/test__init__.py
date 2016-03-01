from __future__ import absolute_import

import pyxs

from . import virtualized


@virtualized
def test_monitor():
    with pyxs.monitor() as m:
        # FAILS!
        m.watch(b"@introduceDomain", b"token")
