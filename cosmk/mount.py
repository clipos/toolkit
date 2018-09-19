# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

"""Module providing mount point management objects.

The host system must provide a ``mount(8)`` and ``umount(8)`` command line
utilities available through PATH.

"""

import os
import tempfile
from types import TracebackType
from typing import List, Optional, Type

from .commons import run
from .exceptions import CosmkError, SystemCommandError


class Mountpoint(object):
    """Mountpoint object that can be used as a context manager for
    contextualized mounts."""

    def __init__(self,
                 source: str,
                 target: str,
                 type: Optional[str] = None,
                 options: Optional[List[str]] = None) -> None:
        # Note: source is not always a path to a device or an existing fs node
        # (e.g. "overlayfs" dummy source value)
        self.source = source
        self.target = os.path.abspath(target)
        self.type = type
        if options and any(("," in x for x in options)):
            raise ValueError(
                "A mount option contains a comma which serves as a separator "
                "for the mount options in the underlying mount command. "
                "Therefore, it cannot be used as part of any mount option.")
        self.options = options

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))

    def __str__(self) -> str:
        return repr(self)

    def __enter__(self) -> "Mountpoint":
        mount(source=self.source, target=self.target, type=self.type,
              options=self.options)
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        umount(target=self.target)


def mounts() -> List[Mountpoint]:
    """Return the list of the mount points in the current mnt namespace. In
    other words, it basically wraps the contents of the pseudo-file
    ``/proc/mounts`` into an easily manipulable Python object."""

    def unescape_whitespaces(s: str) -> str:
        """Unescape the whitespace escaping done to avoid word splitting."""
        # tricky decoding, see: https://stackoverflow.com/a/24519338
        return s.encode("latin-1").decode("unicode_escape")

    mountpoints_list = []
    with open("/proc/mounts") as fp:
        for line in fp.readlines():
            try:
                source, target, type, optionsline, _, _ = line.split()
            except:
                raise CosmkError(
                    "unexpected mount specification from \"/proc/mounts\"")
            options = optionsline.split(",")
            source = unescape_whitespaces(source)
            target = unescape_whitespaces(target)
            options = [unescape_whitespaces(x) for x in options]
            mountpoints_list.append(
                Mountpoint(source=source, target=target, type=type,
                           options=options)
            )
    return mountpoints_list


def mount(source: str,
          target: str,
          type: Optional[str] = None,
          options: Optional[List[str]] = None) -> None:
    """Mount function with usage reflecting the traditional UNIX ``mount(8)``
    command line utility.

    :raises SystemCommandError:
        in case of failure of the ``mount`` call (reason inside the exception)

    """

    mount_cmdline = ["mount"]
    if type:
        mount_cmdline.extend(["-t", type])
    if options:
        if any(("," in x for x in options)):
            raise ValueError(
                "A mount option contains a comma which serves as a separator "
                "for the mount options in the underlying mount command. "
                "Therefore, it cannot be used as part of any mount option.")
        mount_cmdline.extend(["-o", ",".join(options)])
    mount_cmdline.extend([source, os.path.abspath(target)])
    run(mount_cmdline, timeout=5, check=True)


def umount(target: str) -> None:
    """Unmount function with usage reflecting the traditional UNIX
    ``umount(8)`` command line utility.

    :param target: the mountpoint to unmount

    :raises SystemCommandError:
        in case of failure of the ``umount`` call (reason inside the exception)

    """

    run(["umount", os.path.abspath(target)], timeout=5, check=True)
