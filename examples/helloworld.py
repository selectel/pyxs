# -*- coding: utf-8 -*-
"""
    helloworld
    ~~~~~~~~~~

    A minimal working example, showing :mod:`pyxs` API usage.

    :copyright: (c) 2016 by pyxs authors and contributors,
                    see AUTHORS for more details.
"""

from __future__ import print_function

from pyxs import Client, PyXSError


if __name__ == "__main__":
    with Client() as c:
        # a) write-read.
        c[b"/foo/bar"] = b"baz"
        print(c[b"/foo/bar"])  # ==> "baz"

        # b) exceptions! let's try to read a non-existant path.
        try:
            c[b"/path/to/something/useless"]
        except PyXSError as e:
            print(e)

        # c) okay, time to delete that /foo/bar path.
        del c[b"/foo/bar"]

        try:
            c[b"/foo/bar"]
        except PyXSError as e:
            print("`/foo/bar` is no moar!")

        # d) directory listing and permissions.
        c.mkdir(b"/foo/bar")
        c.mkdir(b"/foo/baz")
        c.mkdir(b"/foo/boo")
        print("Here's what `/foo` has: ", c.list(b"/foo"))
        print(c.get_perms(b"/foo"))

        # e) let's watch some paths!
        c.write(b"/foo/bar", b"baz")
        with c.monitor() as m:
            m.watch(b"/foo/bar", b"baz")
            print("Watching ... do ``xenstore-write /foo/bar <anything>``.")
            print(next(m.wait()))  # 1st.
            print(next(m.wait()))  # 2nd.
            m.unwatch(b"/foo/bar", b"baz")

        # f) domain management commands.
        print(c.get_domain_path(0))
        print("domain 0 introduced: ", c.is_domain_introduced(0))

        # g) transactions.
        print("Creating a `/bar/foo` within a transaction.")
        while True:
            c.transaction()
            c[b"/bar/foo"] = b"baz"
            if c.commit():
                break

        print("Transaction committed. Let's check it: "
              "/bar/foo =", c[b"/bar/foo"])
