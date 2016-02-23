import string

import pytest

from pyxs.exceptions import InvalidPath, InvalidPermission
from pyxs.helpers import check_path, check_watch_path, check_perms


def test_check_path():
    # a) max length is bounded by 3072 for absolute path and 2048 for
    #    relative ones.
    with pytest.raises(InvalidPath):
        check_path(b"/foo/bar" * 3072)

    with pytest.raises(InvalidPath):
        check_path(b"foo/bar" * 2048)

    # b) ASCII alphanumerics and -/_@ only!
    for char in string.punctuation:
        if char in "-/_@":
            continue

        with pytest.raises(InvalidPath):
            check_path(b"/foo" + char.encode())

    # c) no trailing / -- except for root path.
    with pytest.raises(InvalidPath):
        check_path(b"/foo/")

    # d) no //'s!.
    with pytest.raises(InvalidPath):
        check_path(b"/foo//bar")

    # e) OK-case.
    check_path(b"/")


def test_check_watch_path():
    # a) ordinary path should be checked with `check_path()`
    with pytest.raises(InvalidPath):
        check_watch_path(b"/foo/")

    with pytest.raises(InvalidPath):
        check_watch_path(b"/fo\x07o")

    with pytest.raises(InvalidPath):
        check_watch_path(b"/$/foo")

    # b) special path options are limited to `@introduceDomain` and
    #    `@releaseDomain`.
    with pytest.raises(InvalidPath):
        check_watch_path(b"@foo")

    # c) OK-case.
    check_watch_path(b"@introduceDomain")
    check_watch_path(b"@releaseDomain")


def test_check_perms():
    # A valid permission has a form `[wrbn]:digits:`.
    with pytest.raises(InvalidPermission):
        check_perms([b"foo"])

    with pytest.raises(InvalidPermission):
        check_perms([b"f20"])

    with pytest.raises(InvalidPermission):
        check_perms([b"r-20"])

    # OK-case
    check_perms(b"w0 r0 b0 n0".split())
    check_perms([b"w999999"])  # valid, even though it overflows int32.
