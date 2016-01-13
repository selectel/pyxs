# -*- coding: utf-8 -*-
"""
    helloworld
    ~~~~~~~~~~

    A minimal working example, showing :mod:`pyxs` API usage.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import unicode_literals, print_function

from pyxs import Client, PyXSError


def run(**kwargs):
    with Client(**kwargs) as c:
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
        print("Here's what `/foo` has: ", c.ls(b"/foo"))
        print(c.get_permissions(b"/foo"))

        # e) let's watch some paths!
        c.write(b"/foo/bar", b"baz")
        with c.monitor() as m:
            m.watch(b"/foo/bar", b"baz")
            print("Watching ... do `$ xenstore-write /foo/bar <anything>`.")
            print(m.wait())
            m.unwatch(b"/foo/bar", b"baz")

        # f) domain managment commands.
        print(c.get_domain_path(0))
        print(c.is_domain_introduced(0))

        # g) transactions.
        with c.transaction() as t:
            print("Creating a `/bar/foo` within a transaction.")
            t.write(b"/bar/foo", b"baz")

        print("Transaction is over -- let's check it: "
              "/bar/foo =", c.read(b"/bar/foo"))

print("Using Unix domain socket connection:")
print("------------------------------------")
run(unix_socket_path="/var/run/xenstored/socket")

print("")

print("Using XenBus connection:")
print("------------------------")
run(xen_bus_path="/proc/xen/xenbus")
