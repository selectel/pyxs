# -*- coding: utf-8 -*-
"""
    pyxs.helpers
    ~~~~~~~~~~~~

    Implements various helpers.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import unicode_literals

__all__ = ["dict_merge", "validate_path", "validate_watch_path",
           "validate_perms", "force_bytes"]

import re
import posixpath
from future_builtins import map

from .exceptions import InvalidPath, InvalidPermission


def dict_merge(*dicts):
    """Merges given dicts to a single one.

    >>> dict_merge()
    {}
    >>> dict_merge({"foo": "bar", "baz": "boo"})
    {'foo': 'bar', 'baz': 'boo'}
    """
    base = {}
    map(base.update, dicts)
    return base


def validate_path(path):
    """Checks if a given path is valid, see
    :exc:`~pyxs.exceptions.InvalidPath` for details.

    :param bytes path: path to check.
    :raises pyxs.exceptions.InvalidPath: when path fails to validate.
    """
    # Paths longer than 3072 bytes are forbidden; clients specifying
    # relative paths should keep them to within 2048 bytes.
    max_len = 3072 if posixpath.abspath(path) else 2048

    if not (re.match("^[a-zA-Z0-9-/_@]+\x00?$", path) and
            len(path) <= max_len):
        raise InvalidPath(path)

    # A path is not allowed to have a trailing /, except for the
    # root path and shouldn't have dount //'s.
    if (len(path) > 1 and path[-1] == b"/") or b"//" in path:
        raise InvalidPath(path)

    return path


def validate_watch_path(wpath):
    """Checks if a given watch path is valid -- it should either be a
    valid path or a special, starting with ``@`` character.

    :param bytes wpath: watch path to check.
    :raises pyxs.exceptions.InvalidPath: when path fails to validate.
    """
    if (wpath.startswith(b"@") and not
        re.match(b"^@(?:introduceDomain|releaseDomain)\x00?$", wpath)):
        raise InvalidPath(wpath)
    else:
        validate_path(wpath)

    return wpath


def validate_perms(perms):
    """Checks if a given list of permision follows the format described
    in :meth:`~pyxs.client.Client.get_perms`.

    :param list perms: permissions to check.
    :raises pyxs.exceptions.InvalidPermissions:
        when any of the permissions fail to validate.
    """
    for perm in perms:
        if not re.match(b"[wrbn]\d+", perm):
            raise InvalidPermission(perm)

    return perms


def force_bytes(value):
    """Coerces a given value to :func:`bytes`.

    >>> force_bytes(u"foo")
    b'foo'
    >>> force_bytes(None)
    b'None'
    """
    if isinstance(value, bytes):
        return value

    if isinstance(value, unicode):
        return value.encode("utf-8")
    else:
        return bytes(value)
