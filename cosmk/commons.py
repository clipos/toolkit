# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""Miscellanous utility functions and helpers that may be used globally in this
package."""

import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
from typing import IO, AnyStr, List, Optional, Tuple, Union

from .exceptions import CosmkEnvironmentError, SystemCommandError

# The regular expression matching a valid environment variable name:
ENVVAR_FORMAT_RE = re.compile(r'^[a-zA-Z\_][a-zA-Z0-9\_]*$')

# Regular expressions validating the product and recipe names and the
# identifier format (which must validate also when used with placeholder such
# as "{{product}}" or "{{recipe}}"):
PRODUCT_NAME_RE = re.compile(r'^[a-zA-Z0-9\_]+$')
RECIPE_NAME_RE = re.compile(r'^[a-zA-Z0-9\_]+$')
RECIPE_IDENTIFIER_RE = re.compile(r'^[^\s/]+/[^\s/]+$')


def rewrap(msg: str) -> str:
    """Rewrap a message by stripping the unneeded indentation and removing
    leading and trailing whitespaces."""
    return textwrap.dedent(msg).strip()


def line(msg: str) -> str:
    """Rewrap a message by stripping the unneeded indentation, removing leading
    and trailing whitespaces and joining all the lines into one unique text
    line.

    >>> line('''
            A potentially long message that
            can overflow the 79 chars limit
            of PEP 8.
    ''')
    "A potentially long message that can overflow the 79 chars limit of PEP 8."

    """
    return ' '.join([line.strip() for line in msg.split("\n")
                                  if len(line.strip())])


def is_tty_attached() -> bool:
    """Checks if the current process is attached to a TTY (*i.e.* if both
    ``stdin``, ``stdout`` and ``stderr`` are TTY)."""

    return all((os.isatty(fd) for fd in [sys.stdin.fileno(),
                                         sys.stdout.fileno(),
                                         sys.stderr.fileno()]))


def linux_version() -> Tuple[int,int,int]:
    """Returns the current Linux kernel version under the form of a 3-tuple of
    int (*e.g.* on a ``4.16.12-1-ARCH`` Linux kernel, this function will return
    the tuple :py:data:`(4, 16, 12)`).

    :raise CosmkEnvironmentError: in case the underlying system does not run
        a Linux kernel or if the kernel version string is unparseable

    """

    if platform.system() != 'Linux':
        raise CosmkEnvironmentError("not running a Linux kernel")

    try:
        kver_split = re.search(r'^(\d+)\.(\d+)(\.(\d+))?.*',
                               platform.release())
        # ignore type checking on the following because all exceptions are
        # caught if this ever fails:
        major = int(kver_split.group(1))
        minor = int(kver_split.group(2))
        micro = int(kver_split.group(4)) if kver_split.group(3) else 0 # type: ignore
    except:
        raise CosmkEnvironmentError(
            "unexpected Linux kernel version string {!r}".format(
                platform.release()))

    return (major, minor, micro)


def run(cmd: Union[List[str], str],
        terminal: bool = False,
        stdout: Optional[IO[AnyStr]] = None,
        stderr: Optional[IO[AnyStr]] = None,
        stdouterr: Optional[IO[AnyStr]] = None,
        timeout: Optional[int] = None,
        check: bool = True,
        outside_of_virtualenv: bool = True) -> None:
    """Wrapper around the ``submodule.run`` function with capture of the output
    streams (``stdout``, ``stderr`` or both streams interlaced as one).

    :param cmd: the command line to run (either in the form of a sh-escaped
        command line string or a list of arguments as `subprocess` takes)
    :param terminal: whether or not the terminal shall be forwarded to the
        command
    :param stdout: file-object receiving the capture of the command ``stdout``
        output stream
    :param stderr: file-object receiving the capture of the command ``stderr``
        output stream
    :param stdouterr: file-object receiving the capture of the command output
        stream with both ``stdout`` and ``stderr`` interlaced (*i.e.* as it
        appears in an interactive shell without output redirection)
    :param timeout: the time out value to apply to the command run
    :param check: raise an exception if the command exits with a non-null
        return value
    :param outside_of_virtualenv: if running from a virtualenv, then this
        parameter will strip all the parameters proper to the virtualenv from
        the environment variable set to be given to the process to run

    .. note::
       The function detects if ``cosmk`` is run from a virtualenv by looking
       the value of the ``VIRTUAL_ENV`` environment variable.

    :raise ValueError: if bad parameters are given to this function
    :raise SystemCommandError: in case of failure when executing the command

    """

    # Inherit by default the environment of cosmk:
    env = dict(os.environ)  # use dict to avoid modifying current environment

    try:
        if outside_of_virtualenv and env["VIRTUAL_ENV"]:
            # Retrieve path to the virtualenv and all the items composing PATH:
            venv_path = env["VIRTUAL_ENV"]
            path_items = env["PATH"].split(":")
            new_path_items = path_items[:]  # copy object to receive changes

            # Iterate on the PATH items and strip all items beginning by the
            # virtualenv path (using canonical paths):
            for path_component in path_items:
                if os.path.realpath(path_component).startswith(
                        os.path.realpath(venv_path)):
                    new_path_items.remove(path_component)

            # Unset VIRTUAL_ENV and set new PATH (with virtualenv binaries path
            # stripped):
            del env["VIRTUAL_ENV"]
            env['PATH'] = ':'.join(new_path_items)
    except KeyError:
        # if we land here, then either PATH or VIRTUAL_ENV is missing in the
        # environment, proceed silently (even if this is strange...)
        pass

    # split the command into a list of arguments as expected by subprocess
    cmd_split = shlex.split(cmd) if isinstance(cmd, str) else cmd
    if len(cmd_split) < 1:
        raise ValueError("You cannot provide an empty command line.")

    # Special case if we need to forward the current TTY:
    if terminal:
        if any([stdout, stderr, stdouterr]):
            raise ValueError(line(
                """You cannot provide both file-object to capture any command
                output and run the command in the current terminal."""))
        try:
            subprocess.run(cmd_split, timeout=timeout, check=check, env=env)
        except FileNotFoundError:
            raise SystemCommandError(cmd_split, "Command not found in PATH")
        except subprocess.TimeoutExpired:
            raise SystemCommandError(cmd_split, "Timed out")
        except subprocess.CalledProcessError as exc:
            raise SystemCommandError(cmd_split,
                                     reason="Returned exit value {}"
                                        .format(exc.returncode))
    else:
        if stdouterr and (stdout or stderr):
            raise ValueError(line(
                """You cannot provide both file-object to capture the command
                output (stdout and stderr mixed together) and on the same time
                a file-object to capture either stdout or stderr."""))

        # Note for the following, we need to use a tempfile.TemporaryFile
        # rather than a io.StringIO since StringIO does not implement the
        # fileno() method and this is required by the way subprocess module is
        # implemented.

        if not any([stdout, stderr, stdouterr]) or stdouterr:
            # Case where output is mixed (stdout and stderr interlaced)
            try:
                # assume already opened by caller if provided
                stdouterr_fp = (tempfile.TemporaryFile("w+")
                                if not stdouterr else stdouterr)
                subprocess.run(cmd_split, stdout=stdouterr_fp,
                               stderr=stdouterr_fp, timeout=timeout,
                               check=check, env=env)
            except FileNotFoundError:
                raise SystemCommandError(cmd_split,
                                         "Command not found in PATH")
            except subprocess.TimeoutExpired:
                raise SystemCommandError(cmd_split,
                                         "Timed out")
            except subprocess.CalledProcessError as exc:
                stdouterr_fp.seek(0)  # rewind file for reading
                raise SystemCommandError(cmd_split,
                                         reason="Returned exit value {}"
                                            .format(exc.returncode),
                                         stdouterr=stdouterr_fp.read())
            finally:
                if not stdouterr:
                    stdouterr_fp.close()
        else:
            try:
                # assume already opened by caller if provided
                stdout_fp = (tempfile.TemporaryFile("w+")
                             if not stdout else stdout)
                try:
                    # assume already opened by caller if provided
                    stderr_fp = (tempfile.TemporaryFile("w+")
                                 if not stderr else stderr)
                    subprocess.run(cmd_split, stdout=stdout_fp,
                                   stderr=stderr_fp, timeout=timeout,
                                   check=check, env=env)
                except FileNotFoundError:
                    raise SystemCommandError(cmd_split,
                                            "Command not found in PATH")
                except subprocess.TimeoutExpired:
                    raise SystemCommandError(cmd_split, "Timed out")
                except subprocess.CalledProcessError as exc:
                    stdout_fp.seek(0)  # rewind file for reading
                    stderr_fp.seek(0)  # rewind file for reading
                    raise SystemCommandError(cmd_split,
                                             reason="Returned exit value {}"
                                                 .format(exc.returncode),
                                             stdout=stdout_fp.read(),
                                             stderr=stderr_fp.read())
                finally:
                    if not stderr:
                        stderr_fp.close()
            finally:
                if not stdout:
                    stdout_fp.close()
