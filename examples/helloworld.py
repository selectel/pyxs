# -*- coding: utf-8 -*-
"""
    helloworld
    ~~~~~~~~~~

    A minimal working example, showing :mod:`pyxs` API usage.
"""

from __future__ import unicode_literals, print_function

from pyxs import Connection

c = Connection("/var/run/xenstored/socket")

# a) read.
p = c.read(b"/local/domain/0/domid")
print(p.payload)  # ==> 0, which is just what we expect.

# b) write-read.
p = c.write(b"/foo/bar", b"baz")
p = c.read(b"/foo/bar")
print(p.payload)  # ==> "baz"

# c) exceptions! let's try to read a non-existant path.
try:
    c.read(b"/path/to/something/useless")
except RuntimeError as e:
    print(e)

# d) okay, time to delete that /foo/bar path.
p = c.rm(b"/foo/bar")

try:
    c.read(b"/foo/bar")
except RuntimeError as e:
    print("`/foo/bar` is no moar!")
