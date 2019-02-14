# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

import pwd
import os
import warnings
from types import TracebackType
from typing import List, Optional, Tuple, Type, Union

from .exceptions import CosmkError
from .log import critical, debug, error, info, warn


def init_lower_privileges(uid: int, gid: int) -> None:
    """Function to lower privileges (*i.e.* change *real* and *effective* UIDs
    and GIDs to UID/GID values given as arguments) intended to be called at
    cosmk module importation."""

    # Reset the supplementary groups of the current user to the supplementary
    # groups of the target unprivileged user:
    username = pwd.getpwuid(uid).pw_name
    usergroups = os.getgrouplist(username, gid)
    os.setgroups(usergroups)
    # And then hange real, effective and saved-set UID and GID:
    os.setresgid(gid, gid, 0)  # GID before UID otherwise this fails
    os.setresuid(uid, uid, 0)


class ElevatedPrivileges(object):
    """Context manager class to be used to elevate privileges locally within
    Python code of this cosmk module."""

    @staticmethod
    def possible() -> bool:
        """Evaluates if the privileges elevation is possible by doing a
        RES{U,G}ID flip over."""
        resuid = os.getresuid()
        resgid = os.getresgid()
        return (
            (resuid[2], resgid[2]) == (0, 0) and resuid[0] != 0 and
            resuid[1] != 0 and resgid[0] != 0 and resgid[0] != 0
        )

    def __enter__(self) -> Tuple[int, int]:
        current_uid = os.geteuid()
        current_gid = os.getegid()
        if current_uid == 0 or current_gid == 0:
            raise CosmkError("nested privileges elevations do not work")
        os.setresgid(0, 0, current_gid)  # GID before UID otherwise this fails
        os.setresuid(0, 0, current_uid)
        self.current_mask = os.umask(0o022)
        return (current_uid, current_gid)

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        os.umask(self.current_mask)
        unprivileged_uid = os.getresuid()[2]  # retrieve saved-set-UID
        unprivileged_gid = os.getresgid()[2]  # retrieve saved-set-GID
        os.setresuid(unprivileged_uid, unprivileged_uid, 0)
        os.setresgid(unprivileged_gid, unprivileged_gid, 0)
