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


def main(client, top):
    depth = top.count("/")

    for path, value, children in client.walk(top):
        if path == top: continue

        node = posixpath.basename(path) or "/"
        print("{0}{1} = \"{2}\"".format(" " * (path.count("/") - depth - 1),
                                        node, value))


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

    main(Client(connection=connection), path)
