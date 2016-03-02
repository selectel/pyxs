# -*- coding: utf-8 -*-
"""
    monitor
    ~~~~~~~

    A simple monitor, which fires a callback each time a new domains
    is introduced or released from XenStore.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

import pyxs

with pyxs.monitor() as m:
    m.watch(b"@introduceDomain", b"unused")
    m.watch(b"@releaseDomain", b"unused")

    for wpath, _token in m.wait():
        # Funny thing is -- XenStored doesn't send us domid of the
        # event target, so we have to get it manually, via ``xc``.
        if wpath == b"@introduceDomain":
            print("Hey, we got a new domain here!")
        else:
            print("Ooops, we lost him ...")
