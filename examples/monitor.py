# -*- coding: utf-8 -*-
"""
    monitor
    ~~~~~~~

    A simple monitor, which fires a callback each time a new domains
    is introduced or released from XenStore.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from pyxs import monitor


with monitor() as m:
    m.watch("@introduceDomain", "introduced")
    m.watch("@releaseDomain", "released")

    _, token = m.wait(sleep=.1)

    # Funny thing is -- XenStored doesn't send us domid of the
    # event target, so we have to get it manually, via ``xc``.
    if token == "introduced":
        print("Hey, we got a new domain here!")
    else:
        print("Ooops, we lost him ...")
