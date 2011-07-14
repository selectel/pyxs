# -*- coding: utf-8 -*-
"""
    helloworld
    ~~~~~~~~~~

    A minimal working example, showing :mod:`pyxs` API usage.
"""

from __future__ import unicode_literals, print_function

from pyxs import Client, PyXSError


with Client() as c:
    # a) write-read.
    c.write(b"/foo/bar", b"baz")
    print(c.read(b"/foo/bar"))  # ==> "baz"

    # b) exceptions! let's try to read a non-existant path.
    try:
        c.read(b"/path/to/something/useless")
    except PyXSError as e:
        print(e)

    # c) okay, time to delete that /foo/bar path.
    c.rm(b"/foo/bar")

    try:
        c.read(b"/foo/bar")
    except PyXSError as e:
        print("`/foo/bar` is no moar!")

    # d) directory listing and permissions.
    c.mkdir(b"/foo/bar")
    c.mkdir(b"/foo/baz")
    c.mkdir(b"/foo/boo")
    print(c.directory(b"/foo"))
    print(c.get_perms(b"/foo"))

    # e) let's watch some paths!
    c.write(b"/foo/bar", b"baz")
    c.watch(b"/foo/bar", "baz")
    print("Watching ... do `$ xenstore-write /foo/bar <anything>`.")
    print(c.wait())
    c.unwatch(b"/foo/bar", "baz")

    # f) domain managment commands.
    print(c.get_domain_path(0))
    print(c.is_domain_introduced(0))

    # g) transactions.
    with c.transaction() as t:
        print("Creating a `/bar/foo` within a transaction.")
        t.write("/bar/foo", "baz")

    print("Transaction is over -- let's check it: "
          "/bar/foo =", c.read("/bar/foo"))
