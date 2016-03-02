# -*- coding: utf-8 -*-
"""
    ls
    ~~

    ``xenstore-ls`` implementation with :mod:`pyxs`.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import print_function

import posixpath
import sys

from pyxs.client import Client


def main(client, top):
    # ``xenstore-ls`` doesn't render top level.
    depth = top.count(b"/") + (top != b"/")

    for path, value, children in client.walk(top):
        if path == top:
            continue

        node = posixpath.basename(path)
        indent = " " * (path.count(b"/") - depth)
        print("{0}{1} = \"{2}\"".format(indent, node, value))


if __name__ == "__main__":
    try:
        [path] = sys.argv[1:] or ["/"]
    except ValueError:
        sys.exit("usage: %prog PATH")

    with Client() as client:
        main(client, posixpath.normpath(path).encode())
