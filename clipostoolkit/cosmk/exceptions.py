# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""CLIP OS toolkit exceptions"""

import shlex
from typing import List, Optional, Union


class CosmkError(Exception):
    """Base exception for all the other cosmk related exceptions. This
    exception can also be raised when the error is unknown or unhandled by the
    tool."""
    pass

class CosmkEnvironmentError(CosmkError):
    """Exception raised when the runtime environment does not meet the
    requirements to run properly (*e.g.* a system utility command is
    missing)."""
    pass

class UnexpectedRepoSourceTreeStructure(CosmkError):
    """Exception raised when the repo directory structure does not match what
    is expected or when the ".repo" directory cannot be found in the underlying
    directory tree of the current working directory."""
    pass

class InstrumentationSpecificationError(CosmkError):
    """Exception raised when the "instrumentation.toml" drop-in file is badly
    formatted or has unexpected content."""
    pass

class ProjectInRepoSourceTreeInUncleanState(CosmkError):
    """Exception raised when a project within the CLIP OS repo source tree is
    not in a clean state (*e.g.* unstaged elements)."""
    pass

class RepoSourceTreeManifestParsingError(CosmkError):
    """Exception raised when a ``repo`` manifest file has an unexpected XML
    structure or cannot be parsed as valid XML."""
    pass

class SdkNotFoundError(CosmkError):
    """Exception raised when a target requires a SDK which cannot be found
    because it has not been bootstrap (*i.e.* built) yet."""
    pass

class SdkBootstrapError(CosmkError):
    """Exception raised when an error occurs while bootstrapping a SDK
    image."""
    pass

class SdkError(CosmkError):
    """Exception raised when an error occurs inside a SDK container."""
    pass

class ProductPropertiesError(CosmkError):
    """Exception raised when a product has a bad "properties.toml"
    definition."""
    pass

class RecipeConfigurationError(CosmkError):
    """Exception raised when a recipe has a bad "recipe.toml" definition."""
    pass

class RecipeActionError(CosmkError):
    """Exception raised when a recipe has a bad "recipe.toml" definition."""
    pass

class SystemCommandError(CosmkError):
    """Exception raised when a system command (such as ``mount(8)`` or
    ``losetup(8)``) fails. Reason should be provided as arguments to the
    exception."""

    def __init__(self,
                 command: Union[str, List[str]],
                 reason: Optional[str] = None,
                 stdout: Optional[str] = None,
                 stderr: Optional[str] = None,
                 stdouterr: Optional[str] = None) -> None:
        # stringify the command if ever provided as a subprocess command list
        if isinstance(command, list):
            self.command = " ".join([shlex.quote(arg) for arg in command])
        else:
            self.command: str = command
        if not any([reason, stdout, stderr, stdouterr]):
            raise ValueError(
                "A reason of failure or an output of the failed command must "
                "be provided.")
        self.reason = reason
        if stdouterr and (stdout or stderr):
            raise ValueError(
                "You cannot provide both a mixed output (stdout+stderr) and "
                "on the same time either stdout or stderr.")
        self.stdout = stdout
        self.stderr = stderr
        self.stdouterr = stdouterr

    def __str__(self) -> str:
        text = "Command {!r} failed.".format(self.command)
        if self.reason:
            text += "\nReason of failure: {}".format(self.reason)
        if self.stdout:
            text += "\n v-- stdout --v\n{}\n ^-- end of stdout --^".format(
                self.stdout)
        if self.stderr:
            text += "\n v-- stderr --v\n{}\n ^-- end of stderr --^".format(
                self.stderr)
        if self.stdouterr:
            text += ("\n v-- mixed output (stdout+stderr) --v\n"
                     "{}\n ^-- end of output --^").format(self.stdouterr)
        return text

class ContainerSnapshotError(CosmkError):
    """Exception raised when a container sesssion snapshotting fails."""
    pass

class VirtualizedEnvironmentError(CosmkError):
    """Exception raised when an operation on a virtualized environment (*e.g.*
    a `libvirt` "domain") cannot be pursued or has failed."""
    pass
