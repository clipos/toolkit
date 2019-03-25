# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""cosmk: The CLIP OS (and derivatives) build tool"""

import argparse
import atexit
import os
import shutil
import sys
import traceback
from typing import Any, Dict

import argcomplete

from .commons import line
from .completion import product_completer, recipe_completer
from .exceptions import CosmkError
from .healthcheck import healthcheck
from .log import critical, debug, error, info, warn
from .privileges import ElevatedPrivileges
from .product import Product
from .recipe import Recipe
from .sourcetree import (fix_output_nodes_ownerships, repo_root_path,
                         snapshot_manifest)


def main(as_module: bool = False) -> None:
    """Main function of the cosmk command-line utility.

    :param as_module: `True` when called as a module (*e.g.* ``python -m
        cosmk``)

    """

    parser = argparse.ArgumentParser(description=__doc__)

    # global arguments
    parser.add_argument(
        '-d', '--debug',
        help="enables the display of debug messages",
        action="store_true",
        default=False
    )
    parser.add_argument(
        '--no-sudo',
        help="do not try to elevate privileges by recalling itself via sudo",
        action="store_true",
        default=False
    )

    subparsers = parser.add_subparsers(
        title='subcommands',
        dest='subcommand',
        metavar='<subcommand>'
    )

    # All the subcommands recognized by cosmk follows:
    # Note: argparse respects the order of declaration of these subcommands, so
    # ensure to list them from the most used to the least.

    # We deliberatly ignore typing checks on `add_argument` calls because
    # argcomplete modifies/extends the argparse classes and this is confusing
    # for mypy since argcomplete does not provide the typeshed extensions...

    subparsers.add_parser(
        "repo-root-path",
        help="outputs on stdout the repo root absolute path",
    )

    subparsers.add_parser(
        "healthcheck",
        help="verify the current system meet the cosmk requirements"
    )

    snapshot_sp = subparsers.add_parser(
        "snapshot",
        help="snapshot the current repo manifest file to the current state",
        description=line(
            """Take a snapshot of the current CLIP OS source tree (i.e. the
            repo root) by fixing the Git commit hashes of all the git projects
            defining a state of development of this source tree in the manifest
            files currently in use by repo.  Modifications will be brought in
            the "manifest" repository at the root of this source tree. The
            various projects must be in a clean Git status and the manifest
            project at the root of the source tree must be synchronized with
            the manifest revision currently referenced by repo. These
            requirements are automatically checked before modifying the
            manifest files. Committing the manifest file is still of your
            responsibility.""")
    )
    snapshot_sp.add_argument(
        "-b", "--use-branches",
        action="store_true",
        help=line("""use Git branches rather than Git commit hashes in the
                  "snapshotted" manifest file""")
    )

    product_version_sp = subparsers.add_parser(
        "product-version",
        help="outputs on stdout the version for the given product",
    )
    product_version_sp.add_argument(  # type: ignore
        "product",
        metavar="<product>",
        help="the product from which to get the version"
    ).completer = product_completer


    bootstrap_sp = subparsers.add_parser(
        "bootstrap",
        help="bootstrap a SDK recipe from a recipe-specified archive file"
    )
    bootstrap_sp.add_argument(  # type: ignore
        "recipe",
        metavar="<recipe>",
        help="the SDK recipe to bootstrap"
    ).completer = recipe_completer

    run_sp = subparsers.add_parser(
        "run",
        help="run a recipe implementing the \"run\" recipe feature"
    )
    run_sp.add_argument(  # type: ignore
        "recipe",
        metavar="<recipe>",
        help="the recipe to run"
    ).completer = recipe_completer
    run_sp.add_argument(
        "command",
        metavar="<command>",
        nargs="*",
        default=[],
        help=line("""the command to run inside the SDK""")
    )

    build_sp = subparsers.add_parser(
        "build",
        help="build from source the rootfs of a given recipe"
    )
    build_sp.add_argument(  # type: ignore
        "recipe",
        metavar="<recipe>",
        help="the recipe to build"
    ).completer = recipe_completer
    build_sp.add_argument(
        "--clear-cache",
        action="store_true",
        help=line("""clear the cache associated to the given recipe before
                  building""")
    )
    build_sp.add_argument(
        "--no-clear-previous-build",
        action="store_true",
        help=line("""do not clear the previous build result from the output
                  directory (use with caution)""")
    )

    image_sp = subparsers.add_parser(
        "image",
        help=line("""build the rootfs of a given recipe from the cache produced
                  during the "build" action step""")
    )
    image_sp.add_argument(  # type: ignore
        "recipe",
        metavar="<recipe>",
        help="the recipe to image"
    ).completer = recipe_completer

    configure_sp = subparsers.add_parser(
        "configure",
        help="apply a configuration on a given recipe"
    )
    configure_sp.add_argument(  # type: ignore
        "recipe",
        metavar="<recipe>",
        help="the recipe to configure"
    ).completer = recipe_completer

    bundle_sp = subparsers.add_parser(
        "bundle",
        help="bundle a recipe"
    )
    bundle_sp.add_argument(  # type: ignore
        "recipe",
        metavar="<recipe>",
        help="the recipe to bundle"
    ).completer = recipe_completer

    subparsers.add_parser(
        "fix-source-tree-permissions",
        help=line(
            """fix permissions/file ownership of sub-parts of the current CLIP
            OS source tree to the current user"""),
        description=line("""Restore the ownership rights to the current
                         unprivileged user without messing with the file rights
                         of the built rootfs or the container working
                         directories."""),
    )

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    # Grand try..except block to reformat cleanly an eventual uncaught
    # exception.
    try:
        # finish initialization of the logger
        if args.debug:
            from .log import _enable_debug_console
            _enable_debug_console()

        debug("Parsed command line arguments: {!r}".format(args))

        # Some subcommands do not require elevated privileges, treat them here:
        if not args.subcommand:
            error("a subcommand is required")
            parser.print_help()
            sys.exit(1)
        elif args.subcommand == 'repo-root-path':
            print(repo_root_path())
            sys.exit()
        elif args.subcommand == 'product-version':
            product = Product(args.product)
            print(product.version)
            sys.exit()
        elif args.subcommand == 'snapshot':
            # Do not snapshot HEAD status of the "alt" projects (i.e.
            # external/third-party projects because their reference commits
            # belongs elsewhere -- in the Portage tree within CROS_WORKON for
            # instance) and "meta" projects (i.e. such as the manifest clone at
            # the repo root):
            snapshot_manifest(use_branches=args.use_branches,
                              no_snapshot_groups=["alt", "meta"])
            sys.exit()

        # cosmk CLI tool is meant to be run as root (privileges are lowered
        # automatically at initialization in this case): if it is not the case
        # and if sudo is available through PATH, then recall ourselves through
        # sudo
        if (os.geteuid() != 0 and not ElevatedPrivileges.possible() and
                not args.no_sudo and not as_module):
            debug("euid != 0, recalling ourselves through sudo.")
            sudo_ourselves()

        # Some subcommands do not require output nodes ownership fix, treat
        # them here:
        if args.subcommand == 'fix-source-tree-permissions':
            fix_output_nodes_ownerships()
            sys.exit()

        # Register the ownership node fix function when exiting this tool
        debug("registering in advance output nodes ownership fix at exit")
        atexit.register(fix_output_nodes_ownerships)

        if args.subcommand in ('bootstrap', 'run', 'build', 'image',
                               'configure', 'bundle'):
            recipe = Recipe(args.recipe)
            subcommand_kwargs: Dict[str, Any] = {}
            if args.subcommand == 'build':
                subcommand_kwargs = {
                    "clear_cache": args.clear_cache,
                    "clear_previous_build": not args.no_clear_previous_build,
                }
            if args.subcommand == 'run':
                subcommand_kwargs = {
                    "command": " ".join(args.command) if args.command else None,
                }
            getattr(recipe, args.subcommand)(**subcommand_kwargs)
            sys.exit()

        # subcommand sinkhole:
        raise NotImplementedError("subcommand not implemented")

    except CosmkError as exc:
        exctype, text = exc.__class__.__name__, str(exc)
        if text:
            msg_to_log = "{} ({})".format(text, exctype)
        else:
            msg_to_log = "Uncaught exception {}.".format(exctype)
        if args.debug:
            msg_to_log += "\n" + traceback.format_exc()
        critical(msg_to_log)
        sys.exit(1)

    except Exception as exc:
        exctype, text = exc.__class__.__name__, str(exc)
        if text:
            msg_to_log = "Uncaught unknown exception {}:\n{}".format(exctype,
                                                                     text)
        else:
            msg_to_log = "Uncaught unknown exception {}.".format(exctype)
        if args.debug:
            msg_to_log += "\n" + traceback.format_exc()
        critical(msg_to_log)
        sys.exit(1)


def sudo_ourselves() -> None:
    """Replace the current process by recalling the same command that
    originated the current process (using ``sys.argv``) but by calling it
    through ``sudo``.
    In case of success, this function does not return since it calls
    ``execve(2)``.

    The command line that calls ``sudo`` ensures to keep the environment
    variables of the unprivileged user (as well as the contents of ``PATH``
    which can be overwritten by Sudo for safety reasons).

    .. note::
       This requires Sudo 1.8.21 or above.

    :raises CosmkError:
        if ``sudo`` could not be found in PATH or if the call has failed

    """

    sudo_path = shutil.which("sudo")
    if not sudo_path:
        raise CosmkError("\"sudo\" has not been found in PATH")
    try:
        # "--preserve-env=<LIST-OF-VARS>" option appeared in Sudo 1.8.21
        os.execv(sudo_path, ["sudo", "-E", "--preserve-env=PATH"] + sys.argv)
    except BaseException as exc:
        raise CosmkError("\"os.execv\" call has failed")


if __name__ == '__main__':
    main(as_module=True)
