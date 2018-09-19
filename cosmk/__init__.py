# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

"""The CLI tool of the CLIP OS toolkit

.. warning::
    **This module has side-effects on the Python runtime!**

    Since parts of this module and its submodule require super-user rights to
    perform some vital operations (*e.g.* managing Linux containers or creating
    files with all kinds of user rights), this module must be imported from a
    privileged Python runtime (*i.e.* a runtime with ``EUID`` and ``EGID`` both
    equal to *0*).

    The side-effects on the Python runtime are explained by the fact that, on
    import, the *real* and *effective* UIDs and GIDs are changed to some
    unprivileged UID and GID (see *Note* below). This is made to be able to
    operate most of the time without explicit super-user privileges since most
    of the logic of this Python package do not require super-user privileges
    (*e.g.* for managing parts of the CLIP OS sources tree or parsing
    configuration files).

    But as the *saved-set* UID and GID are kept to 0, it is still possible for
    the Python runtime to retrieve privileged *real* and *effective* UIDs and
    GIDs. This super-user privileges retrieval (also inaccurately referenced as
    *privilege elevation*) is done with the context manager
    :class:`cosmk.privileges.ElevatedPrivileges` which temporarily flips the
    values of both *real* and *effective* UIDs and GIDs with the values of
    *saved-set* UID and GID (respectively) and vice versa. This enables us to
    build seamless privileged sections of code without having to invoke
    ``sudo`` or any other method or privileges elevation (that may require user
    intevention such as password entry).

    Please note that this construction was never meant to be a security
    mechanism against unsafe code evaluation as it is still possible to
    retrieve elevated privileges with the same method as the
    `ElevatedPrivileges` context manager does. The only purpose of this was to
    avoid running the whole `cosmk` package and its module dependencies with
    a privileged Python runtime which might cause issues.

    If imported from an unprivileged Python runtime, this module will fail at
    the first attempt of privileges elevation with the context manager
    :class:`cosmk.privileges.ElevatedPrivileges`.

.. note::

    Since the context manager :class:`cosmk.privileges.ElevatedPrivileges`
    requires unprivileged UID and GID to change both *real* and *effective*
    UIDs and GIDs at initialization, this module uses the environment variables
    ``SUDO_UID`` and ``SUDO_GID``. These variables are provided by the famous
    utility ``sudo`` and contain the unprivileged UID and GID. This is the
    reason why the ``cosmk`` utility recalls itself through ``sudo`` when
    launched without super-user privileges.

"""

# builtins import for the small part of code in this __init__ file
import os
import warnings

# The only place where the version of this Python package is defined (setup.py
# reparses only this line for setuptools). This versioning follows semver.
__version__ = "0.1.0"

# Easy access to main objects (classes, modules, functions) of this package
__all__ = [
    "commons",
    "completion",
    "container",
    "exceptions",
    "features",
    "fs",
    "healthcheck",
    "instrumentation",
    "log",
    "mount",
    "privileges",
    "product",
    "recipe",
    "sdk",
    "sourcetree",
    "virt",
]

# Automatic privileges lowering if this module has been imported from a Python
# privileged runtime:
from . import exceptions, privileges, commons
if os.geteuid() == 0 and os.getegid() == 0:
    try:
        uid = int(os.environ["SUDO_UID"])
        gid = int(os.environ["SUDO_GID"])
    except KeyError:
        raise exceptions.CosmkError(commons.line("""
            Could not infer from SUDO_UID and SUDO_GID environment variables
            the UID,GID pair on which to do a privileges lowering"""))
    else:
        privileges.init_lower_privileges(uid, gid)

# Initialize the logging facility for this module (one logger for the whole
# cosmk package).
from . import log
logger = log._create_logger(__name__)
