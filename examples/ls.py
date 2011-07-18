# -*- coding: utf-8 -*-
"""
    ls
    ~~

    ``xenstore-ls`` implementation with :mod:`pyxs`.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import print_function, unicode_literals

import optparse
import posixpath

from pyxs.client import Client, XenBusConnection, UnixSocketConnection
from pyxs.exceptions import PyXSError


def traverse(c, node, prefix=()):
    if not node: return                 # Looks like we've reached the bottom.

    depth = max(0, (len(prefix) - 1) * 2)

    prefix += (node, )                  # Updating prefix with another node ..
    path = posixpath.join(*prefix)      # . and joining the resulting path.

    if path != node:                    # Don't print the root node.
        print("{0}{1} = {2!r}".format(" " * depth, node, c.read(path)))

    for child in c.ls(path):     # Repeat everything for each child.
        traverse(c, child, prefix)


if __name__ == "__main__":
    parser = optparse.OptionParser(usage="%prog [PATH]")
    parser.add_option("--socket", action="store_true",
                      help="connect through Unix socket, instead of XenBus.")

    options, args = parser.parse_args()

    if options.socket:
        connection = UnixSocketConnection()
    else:
        connection = XenBusConnection()

    [path] = args[:1] or ["/"]

    try:
        traverse(Client(connection=connection), path)
    except PyXSError as e:
        print(e)
