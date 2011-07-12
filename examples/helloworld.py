# -*- coding: utf-8 -*-
"""
    helloworld
    ~~~~~~~~~~

    A minimal working example, showing :mod:`pyxs` API usage.
"""

from __future__ import unicode_literals, print_function

from pyxs import Connection

c = Connection("/var/run/xenstored/socket")

# a) debug just prints a given value to ``xenstored`` debug log.
p = c.debug("print", "hello world!" + "\x00")
print(p.payload)  # ==> "OK"

# b) read
p = c.read("/local/domain/0/domid")
print(p.payload)  # ==> 0, which is just what we expect.

# c) write
p = c.write("/foo/bar", "baz")
p = c.read("/foo/bar")
print(p.payload)  # ==> "baz"
