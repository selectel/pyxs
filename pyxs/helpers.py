# -*- coding: utf-8 -*-
"""
    pyxs.helpers
    ~~~~~~~~~~~~

    Implements various helpers.

    :copyright: (c) 2011 by Selectel, see AUTHORS for more details.
"""

from __future__ import unicode_literals

__all__ = ["spec", "compile", "compose", "many", "many_or_none"]

import re
import posixpath
from functools import wraps
from future_builtins import map, zip

from .exceptions import InvalidTerm, InvalidPath, InvalidPermission


re_term = re.compile("""(?x)
    ^<
      (?P<name>\w+?)
      (?P<null_allowed>\|)?
     >
      (?P<null_ending>\|)?
      (?P<repeat>[+*])?
    $""")


def compile(term):
    """Compiles a given term to a name-validator pair, where validator
    is a function of a single argument, capable of validating values
    for `name`.

    .. note:: `reserved` values aren't compiled, since there aren't
              used anywhere but in the DEBUG operation, which is not
              a priority.
    """
    match = re_term.match(term)

    if not match:
        raise InvalidTerm(term)
    else:
        (name,          # Argument name.
         null_allowed,  # Values are allowed to contain NULLs.
         null_ending,   # Values are allowed to have a trailing NULL.
         repeat         # Do we need to repeat previous pattern?
         ) = match.groups()

        regex = re.compile("^{0}+?{1}$".format(
            "[\x20-\x7f\x00]" if null_allowed else "[\x20-\x7f]",
            "\x00" if null_ending else ""
        ).encode("utf-8"))

        if not repeat:
            v = lambda x: regex.match(x)
        elif repeat == "+":
            v = many(regex.match)
        elif repeat == "*":
            v = many_or_none(regex.match)
        else:
            raise InvalidTerm(term)

        v.__name__ = name.encode("utf-8")
        v.null_ending = bool(null_ending)

        return v


def spec(*terms):
    """Decorator, which links a given spec to the wrapped function,
    by updating its ``__spec__`` attribute with a list of validators
    for each spec term. The following symbols can be used in term
    definitions:

    =======  ============================================================
    Symbol   Description
    =======  ============================================================
    ``|``    A ``NULL`` (zero) byte.
    <foo>    A string guaranteed not to contain any ``NULL`` bytes.
    <foo|>   Binary data (which may contain zero or more ``NULL`` bytes).
    <foo>|*  Zero or more strings each followed by a trailing ``NULL``.
    <foo>|+  One or more strings each followed by a trailing ``NULL``.
    ?        Reserved value (may not contain ``NULL`` bytes).
    ??       Reserved value (may contain ``NULL`` bytes).
    =======  ============================================================

    .. note::

       According to ``docs/misc/xenstore.txt`` in the current
       implementation reserved values are just empty strings. So for
       example ``"\\x00\\x00\\x00"`` is a valid ``??`` symbol.
    """
    def decorator(func):
        func.__spec__ = list(map(compile, terms))

        @wraps(func)
        def inner(self, *args):
            args = [force_bytes(a) for a in args]

            for idx, (v, arg) in enumerate(zip(func.__spec__, args)):
                # .. note:: some string arguments are required to
                #           have C-ish null ending, instead of doing
                #           it; which obviously is a mess in Python,
                #           so we do it implicitly inside a decorator.

                # This is a bit dirty of course <_<
                if v.null_ending:
                    args[idx] = arg = append_null(arg)

                if not v(arg):
                    raise ValueError(arg)

                # There's a bunch of 'special' arguments which require
                # extra validation, for instance 'path' and 'perms'.
                if v.__name__ in extra_validators:
                    extra_validators[v.__name__](arg)
            else:
                return func(self, *args)
        return inner
    return decorator


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


def validate_wpath(wpath):
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


#: A dictionary of extra validators for some variable names.
extra_validators = {
    "path": validate_path,
    "wpath": validate_wpath,
    "perms": validate_perms
}


def compose(*fs):
    """Compose any number of one-argument functions into a single one.

    >>> f = compose(sum, lambda x: x + 10)
    >>> f([1, 2, 3])
    16
    """
    return lambda x: reduce(lambda x, f: f(x), fs, x)


def many(f):
    """Convert a one-argument predicate function to a function, which
    takes a various number of arguments and return ``True`` only when
    predicate is truthy for each of them; otherwise ``False`` is
    returned.

    >>> f = many(lambda x: x > 5)
    >>> f([1, 5, 9])
    False
    >>> f([11, 15, 19])
    True
    """
    return lambda xs: len(xs) and many_or_none(f)(xs)


def many_or_none(f):
    """Convert a one-argument predicate function to a gunction, which
    takes a various number of arguments and returns ``True`` when
    predicate is truty for each of them or no arguments were provided;
    otherwise ``False`` is returned.

    >>> f = many_or_none(lambda x: x > 5)
    >>> f([])
    True
    >>> f([11, 15, 19])
    True
    """
    return lambda xs: all(map(f, xs))


def append_null(value):
    """Appends ``NULL`` to string values if they don't yet have one.

    >>> append_null(b"foo")
    b'foo\x00'
    >>> append_null([b"foo", b"bar\x00"])
    [b'foo\x00', b'bar\x00']
    """
    if isinstance(value, basestring) and not value.endswith(b"\x00"):
        return value + b"\x00"
    elif hasattr(value, "__iter__"):
        return list(map(append_null, value))
    else:
        return value


def force_bytes(value):
    """Coerces a given value to :func:`bytes`.

    >>> force_bytes(u"foo")
    b"foo"
    >>> force_bytes([u"foo", 1, None])
    [b'foo', b'1', b'None']
    """
    if isinstance(value, bytes):
        return value

    if isinstance(value, unicode):
        return value.encode("utf-8")
    elif hasattr(value, "__iter__"):
        return list(map(force_bytes, value))
    else:
        return bytes(value)
