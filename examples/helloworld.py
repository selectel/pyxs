# -*- coding: utf-8 -*-
"""
    helloworld
    ~~~~~~~~~~

    A minimal working example, showing :mod:`pyxs` API usage.
"""

from __future__ import unicode_literals, print_function

from pyxs import Client


with Client("/var/run/xenstored/socket") as c:
    # a) read.
    print(
        c.read(b"/local/domain/0/domid")
    )  # ==> 0, which is just what we expect.

    # b) write-read.
    c.write(b"/foo/bar", b"baz")
    print(c.read(b"/foo/bar"))  # ==> "baz"

    # c) exceptions! let's try to read a non-existant path.
    try:
        c.read(b"/path/to/something/useless")
    except RuntimeError as e:
        print(e)

    # d) okay, time to delete that /foo/bar path.
    c.rm(b"/foo/bar")

    try:
        c.read(b"/foo/bar")
    except RuntimeError as e:
        print("`/foo/bar` is no moar!")

    # e) directory listing and permissions.
    print(c.directory(b"/local/domain/0"))
    print(c.get_perms(b"/local/domain/0"))

    # f) let's watch some paths!
    print(c.watch(b"/local/domain/0", "foo"))
    print(c.unwatch(b"/local/domain/0", "foo"))
