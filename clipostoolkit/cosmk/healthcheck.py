# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""CLIP OS toolkit healthcheck functions and stuff"""

import os
import platform
import re

from .exceptions import CosmkEnvironmentError
from .log import debug


def healthcheck() -> None:
    """Verify that the current system has everything to make work properly
    cosmk. This verifies that the Linux kernel version and the available
    features are , the availability of the required system utilities, the filesystem
    options of the repo root underlying mountpoint, the available free space on
    this mountpoint, etc.

    TODO: extend this list :)

    """

    raise NotImplementedError
    #check_system()
    #check_mountpoint()
    #check_pythonenv()


def check_system() -> None:
    if platform.system() != 'Linux':
        raise CosmkEnvironmentError("this tool must run on a Linux machine")

    try:
        # ignore type checking on the following because all exceptions are
        # caught if this ever fails:
        linux_version = re.search(r'^(\d+(\.\d+)*)', platform.release()).group(0) # type: ignore
        linux_version_tuple = tuple((int(k) for k in linux_version.split('.')))
    except:
        raise CosmkEnvironmentError(
            "bad Linux kernel version string returned by platform.release")
    if linux_version_tuple < (4, 4):
        raise CosmkEnvironmentError(
            "cosmk must be run on Linux kernel version 4.4 or above")

    debug("system running Linux {}".format(linux_version))

    # Check kernel features by parsing /proc/config{,.gz}
    raise NotImplementedError
