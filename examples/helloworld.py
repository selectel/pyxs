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
        c.write("/foo/bar", "baz")
        print(c.read("/foo/bar"))  # ==> "baz"

        # b) exceptions! let's try to read a non-existant path.
        try:
            c.read("/path/to/something/useless")
        except PyXSError as e:
            print(e)

        # c) okay, time to delete that /foo/bar path.
        c.rm("/foo/bar")

        try:
            c.read("/foo/bar")
        except PyXSError as e:
            print("`/foo/bar` is no moar!")

        # d) directory listing and permissions.
        c.mkdir("/foo/bar")
        c.mkdir("/foo/baz")
        c.mkdir("/foo/boo")
        print("Here's what `/foo` has: ", c.ls("/foo"))
        print(c.get_permissions("/foo"))

        # e) let's watch some paths!
        c.write("/foo/bar", "baz")
        with c.monitor() as m:
            m.watch("/foo/bar", "baz")
            print("Watching ... do `$ xenstore-write /foo/bar <anything>`.")
            print(m.wait())
            m.unwatch("/foo/bar", "baz")

        # f) domain managment commands.
        print(c.get_domain_path(0))
        print(c.is_domain_introduced(0))

        # g) transactions.
        with c.transaction() as t:
            print("Creating a `/bar/foo` within a transaction.")
            t.write("/bar/foo", "baz")

        print("Transaction is over -- let's check it: "
              "/bar/foo =", c.read("/bar/foo"))

print("Using Unix domain socket connection:")
print("------------------------------------")
run(unix_socket_path="/var/run/xenstored/socket")

print("")

print("Using XenBus connection:")
print("------------------------")
run(xen_bus_path="/proc/xen/xenbus")
