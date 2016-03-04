# -*- coding: utf-8 -*-
"""
    pyxs.helpers
    ~~~~~~~~~~~~

    Implements various helpers.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
    :license: LGPL, see LICENSE for more details.
"""

from __future__ import absolute_import

__all__ = ["check_path", "check_watch_path", "check_perms", "error"]

import errno
import re
import os
import posixpath

from .exceptions import InvalidPath, InvalidPermission, PyXSError


#: A reverse mapping for :data:`errno.errorcode`.
_codeerror = dict((message, code)
                  for code, message in errno.errorcode.items())


def error(smth):
    """Returns a :class:`~pyxs.exceptions.PyXSError` matching a given
    errno or error name.

    >>> error(22)
    pyxs.exceptions.PyXSError: (22, 'Invalid argument')
    >>> error(b"EINVAL")
    pyxs.exceptions.PyXSError: (22, 'Invalid argument')
    """
    if isinstance(smth, bytes):
        smth = _codeerror.get(smth.decode(), 0)

    return PyXSError(smth, os.strerror(smth))


_re_path = re.compile(br"^[a-zA-Z0-9-/_@]+\x00?$")


def check_path(path):
    """Checks if a given path is valid, see
    :exc:`~pyxs.exceptions.InvalidPath` for details.

    :param bytes path: path to check.
    :raises pyxs.exceptions.InvalidPath: when path fails to validate.
    """
    # Paths longer than 3072 bytes are forbidden; clients specifying
    # relative paths should keep them to within 2048 bytes.
    max_len = 3072 if posixpath.abspath(path) else 2048
    if not _re_path.match(path) or len(path) > max_len:
        raise InvalidPath(path)

    # A path is not allowed to have a trailing /, except for the
    # root path and shouldn't have double //'s.
    if (len(path) > 1 and path.endswith(b"/")) or b"//" in path:
        raise InvalidPath(path)

    return path


_re_watch_path = re.compile(br"^@(?:introduceDomain|releaseDomain)\x00?$")


def check_watch_path(wpath):
    """Checks if a given watch path is valid -- it should either be a
    valid path or a special, starting with ``@`` character.

    :param bytes wpath: watch path to check.
    :raises pyxs.exceptions.InvalidPath: when path fails to validate.
    """
    if wpath.startswith(b"@") and not _re_watch_path.match(wpath):
        raise InvalidPath(wpath)
    else:
        check_path(wpath)

    return wpath


_re_perms = re.compile(br"^[wrbn]\d+$")


def check_perms(perms):
    """Checks if a given list of permision follows the format described
    in :exc:`~pyxs.exceptions.InvalidPermissions`.

    :param list perms: permissions to check.
    :raises pyxs.exceptions.InvalidPermissions:
        when any of the permissions fails to validate.
    """
    for perm in perms:
        if not _re_perms.match(perm):
            raise InvalidPermission(perm)

    return perms
