# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

"""Module providing filesystem-related utility functions and classes.

The host system must provide some command line utilities such as ``losetup(8)``
or ``mksquashfs``.

"""

import os
import stat
import sys
import tempfile
from contextlib import contextmanager
from types import TracebackType
from typing import List, Optional, Type, Union

from .commons import line, run
from .exceptions import CosmkError, SystemCommandError
from .mount import Mountpoint


class LoopDevice(object):
    """Simple loop device object abstraction that can be used as a context
    manager."""

    def __init__(self,
                 backfile: str,
                 device: Optional[str] = None,
                 readonly: bool = False) -> None:
        # always use abspath (which are normalized) to simplify comparisons
        self.backfile = os.path.abspath(backfile)
        self.device = os.path.abspath(device) if device else None
        self.readonly = readonly

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))

    def __str__(self) -> str:
        return repr(self)

    def __enter__(self) -> 'LoopDevice':
        open_loop(backfile=self.backfile, device=self.device,
                  readonly=self.readonly)
        # IMPORTANT: refresh our attributes if the loop device node choice has
        # been left to losetup (via open_loop with a None device argument)
        # because the method __exit__ will be needing it to close the loop
        # device!
        try:
            if self.device is None:
                for loopdev in reversed(loop_devices()):
                    if loopdev.backfile == self.backfile:
                        if loopdev.device is None:
                            raise CosmkError(
                                "object has no 'device' attr properly set")
                        self.device = os.path.abspath(loopdev.device)
                        break
                else:
                    raise CosmkError(
                        'could not find the loop device just set up')
        except:
            # cleanup
            self.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        if self.device is None:
            raise CosmkError("object has no 'device' attr properly set")
        close_loop(self.device)


def loop_devices() -> List[LoopDevice]:
    """Get the loop devices currently set up on the system."""

    def unescape_whitespaces(s: str) -> str:
        """Unescape the whitespace escaping done to avoid word splitting."""
        # tricky decoding, see: https://stackoverflow.com/a/24519338
        return s.encode("latin-1").decode("unicode_escape")

    loop_devices_list = []
    losetup_cmd = ["losetup", "-O", "NAME,BACK-FILE,RO", "-n", "-l", "--raw"]
    with tempfile.TemporaryFile("w+") as stdout_fp:
        run(losetup_cmd, stdout=stdout_fp, timeout=5, check=True)
        stdout_fp.seek(0)
        for line in stdout_fp.readlines():
            try:
                device, backfile, ro = line.split()
            except:
                raise SystemCommandError(
                    losetup_cmd,
                    reason="unexpected output line: {}".format(line))
            device = unescape_whitespaces(device)
            backfile = unescape_whitespaces(backfile)
            ro = bool(int(ro))
            loop_devices_list.append(
                LoopDevice(backfile=backfile, device=device, readonly=ro)
            )
    return loop_devices_list


def open_loop(backfile: str,
              device: Optional[str] = None,
              readonly: bool = False) -> None:
    """Open a loopback device given a back-file and eventually the device node
    to use."""

    losetup_cmd = ["losetup"]
    if readonly:
        losetup_cmd.extend(["-r"])
    if device:
        losetup_cmd.extend([os.path.abspath(device)])
    else:
        losetup_cmd.extend(['-f'])
    losetup_cmd.extend([os.path.abspath(backfile)])
    run(losetup_cmd, timeout=5, check=True)


def close_loop(device: str) -> None:
    """Close a loopback device node."""

    losetup_cmd = ["losetup", "-d", os.path.abspath(device)]
    run(losetup_cmd, timeout=5, check=True)


class SquashfsMount(object):
    """Simple squashfs mountpoint object abstraction that can be used as a
    context manager to mount squashfs files onto a given mountpoint."""

    def __init__(self, squashfile: str, mountpoint: str) -> None:
        # always use abspath (which are normalized) to simplify comparisons
        self.squashfile = os.path.abspath(squashfile)
        self.mountpoint = os.path.abspath(mountpoint)

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))

    def __str__(self) -> str:
        return repr(self)

    def __enter__(self) -> 'SquashfsMount':
        self._loopdev = LoopDevice(backfile=self.squashfile, readonly=True)
        self._loopdev = self._loopdev.__enter__()
        try:
            if self._loopdev.device is None:
                raise CosmkError("loop device object has no 'device' set")
            self._mount = Mountpoint(
                source=self._loopdev.device,
                target=self.mountpoint,
                type="squashfs",
                options=['ro']
            )
            self._mount = self._mount.__enter__()
        except:
            self._loopdev.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        self._mount.__exit__(*sys.exc_info())
        self._loopdev.__exit__(*sys.exc_info())


def mksquashfs(squashfs_file: str,
               source_dir: str,
               compressor: str="gzip",
               store_xattrs: bool = True,
               detect_sparse_files: bool = True,
               compress_inode_table: bool = False,
               compress_data_blocks: bool = False,
               compress_fragment_blocks: bool = False,
               compress_extended_attributes: bool = False,
               find_duplicates: bool = False) -> None:
    """Wrapper around the command mksquashfs

    :param squashfs_file: the path to the squashfs file to produce
    :param source_dir: the directory to compress into a squashfs
    :param compressor: the compression method to use
    :param store_xattrs: whether to save extended attributes or not
    :param detect_sparse_files: activate sparse file detection (recommended)
    :param compress_inode_table: compress the inode table
    :param compress_data_blocks: compress data blocks
    :param compress_fragment_blocks: compress fragment blocks
    :param compress_extended_attributes: compress extended attributes
    :param find_duplicates: perform duplicate checking

    """

    if not os.path.isdir(source_dir):
        raise ValueError("source_dir must be a path to a valid directory")

    # For a strange reason, mksquashfs do not overwrite a pre-existing file but
    # do construct the squashfs file somewhere and instantly forget this result
    # (because of the pre-existing squashfs file).
    if os.path.exists(squashfs_file):
        os.remove(squashfs_file)

    mksquashfs_opts = ["-comp", compressor]
    mksquashfs_opts.append("-xattrs" if store_xattrs else "-no-xattrs")
    if not compress_inode_table:
        mksquashfs_opts.append("-noI")
    if not compress_data_blocks:
        mksquashfs_opts.append("-noD")
    if not compress_fragment_blocks:
        mksquashfs_opts.append("-noF")
    if not compress_extended_attributes:
        mksquashfs_opts.append("-noX")
    if not detect_sparse_files:
        mksquashfs_opts.append("-no-sparse")
    if not find_duplicates:
        mksquashfs_opts.append("-noappend")
    mksquashfs_cmd = (["mksquashfs", source_dir, squashfs_file] +
                      mksquashfs_opts)
    run(mksquashfs_cmd, timeout=600)


class OverlayfsMount(object):
    """Simple overlayfs mountpoint object abstraction that can be used as a
    context manager to mount an overlayfs onto a given mountpoint."""

    def __init__(self,
                 mergeddir: str,
                 lowerdir: Union[str, List[str]],
                 upperdir: Optional[str] = None,
                 workdir: Optional[str] = None,
                 options: Optional[List[str]] = None) -> None:
        # always use abspath (which are normalized) to simplify comparisons
        self.mergeddir = os.path.abspath(mergeddir)
        if isinstance(lowerdir, str):
            lowerdir = [lowerdir]
        lowerdir = [os.path.abspath(x) for x in lowerdir]
        if any((":" in x for x in lowerdir)):
            raise ValueError(
                "a path specified as a lowerdir contains a colon which serves "
                "as a separator for the mount command and therefore cannot be "
                "used as part of any lowerdir absolute path")
        self.lowerdir = lowerdir
        if (upperdir and not workdir) or (not upperdir and workdir):
            raise ValueError(
                "upperdir and workdir are interdependent, you must provide "
                "both or none of them")
        self.upperdir = os.path.abspath(upperdir) if upperdir else None
        self.workdir = os.path.abspath(workdir) if workdir else None
        if options and any(((x.startswith("lowerdir=") or
                             x.startswith("upperdir=") or
                             x.startswith("workdir=")) for x in options)):
            raise ValueError(line("""
                                  You cannot provide an additional option which
                                  specify overlayfs lower, upper or work
                                  dir."""))
        self.additional_options = options

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))

    def __str__(self) -> str:
        return repr(self)

    def __enter__(self) -> 'OverlayfsMount':
        options = ["lowerdir=" + ":".join(self.lowerdir)]
        if self.upperdir:
            options.append("upperdir={}".format(self.upperdir))
        if self.workdir:
            options.append("workdir={}".format(self.workdir))
        if self.additional_options:
            options += self.additional_options
        self._mount = Mountpoint(
            source="overlayfs",   # dummy name but required
            target=self.mergeddir,
            type="overlay",
            options=options
        )
        self._mount = self._mount.__enter__()
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        self._mount.__exit__(*sys.exc_info())


class TmpfsMount(object):
    """Simple tmpfs mountpoint object abstraction that can be used as a
    context manager to mount a tmpfs mountpoint."""

    def __init__(self, mountpoint: str, **options: str) -> None:
        # always use abspath (which are normalized) to simplify comparisons
        self.mountpoint = os.path.abspath(mountpoint)
        self.options = options

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))

    def __str__(self) -> str:
        return repr(self)

    def __enter__(self) -> "TmpfsMount":
        self._mount = Mountpoint(
            source="tmpfs",   # dummy name but required
            target=self.mountpoint,
            type="tmpfs",
            options=["{}={}".format(k, v) for k, v in self.options.items()]
        )
        self._mount = self._mount.__enter__()
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        self._mount.__exit__(*sys.exc_info())
