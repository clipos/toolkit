# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""This module provide all the logic, functions and classes to manage the CLIP
OS source tree.
In a greater extent, this CLIP OS source tree is also managed by the ``repo``
tool but this module provide enhanced functionalities to those provided only by
``repo``."""

import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, Optional, Text, Tuple, Union

import git

from .commons import line
from .exceptions import (CosmkEnvironmentError,
                         ProjectInRepoSourceTreeInUncleanState,
                         RepoSourceTreeManifestParsingError,
                         UnexpectedRepoSourceTreeStructure)
from .log import critical, debug, error, info, warn
from .privileges import ElevatedPrivileges

# Usage of a global variable (masked from imports due to the leading
# underscores) are to avoid uneeded recomputation by the function
# repo_root_path() each time it is being called:
__repo_root = None

def is_repo_root(path: str) -> bool:
    """Returns True if the given path contains a ".repo" directory."""
    return os.path.isdir(os.path.join(path, ".repo"))


def repo_root_path() -> str:
    """Guess the repo root directory path from the current working directory or
    (if the CWD does not seem to be a repo root) from the location of the
    cosmk module."""

    global __repo_root
    if __repo_root:
        return __repo_root

    else:
        path = os.path.normpath(os.getcwd())
        while os.path.split(path)[1]:
            if is_repo_root(path):
                break

            path = os.path.split(path)[0]
        else:
            # fallback to the location of this file if the CWD is not in the
            # repo root:
            path = os.path.normpath(os.path.dirname(__file__))
            while os.path.split(path)[1]:
                if is_repo_root(path):
                    break

                path = os.path.split(path)[0]
            else:
                raise UnexpectedRepoSourceTreeStructure(
                    "Could not find repo root!")

        __repo_root = path
        return __repo_root


def fix_output_nodes_ownerships() -> None:
    repo_root = repo_root_path()
    out_path = os.path.join(repo_root, "out")
    cache_path = os.path.join(repo_root, "cache")
    run_path = os.path.join(repo_root, "run")

    debug("Fixing ownership nodes in output (\"out/\") and cache (\"cache/\") "
          "directories...")

    with ElevatedPrivileges() as unprivileged_uid_gid:
        uid, gid = unprivileged_uid_gid

        # <repo_root>/out:
        if os.path.exists(out_path):
            os.chown(out_path, uid, gid)
        for root, dirs, files in os.walk(out_path, topdown=True,
                                         onerror=None, followlinks=False):
            if re.match(r'^out/[^/]+/[^/]+/[^/]+/[^/]+$',
                        os.path.relpath(root, repo_root)):
                # Do not treat the directories in the action output directories
                # as we want to preserve the ownerships of the files contained
                # into those dirs.
                # The following prevents os.walk() from recursing into the
                # child dirs.
                dirs.clear()
            for name in dirs + files:
                if not os.path.islink(os.path.join(root, name)):
                    os.chown(os.path.join(root, name), uid, gid)

        # <repo_root>/cache:
        if os.path.exists(cache_path):
            os.chown(cache_path, uid, gid)
        for root, dirs, files in os.walk(cache_path, topdown=True,
                                         onerror=None, followlinks=False):
            for name in dirs + files:
                os.chown(os.path.join(root, name), uid, gid)

        # <repo_root>/run:
        if os.path.exists(run_path):
            os.chown(run_path, uid, gid)


def snapshot_manifest(
        use_branches: bool = False,
        snapshot_groups: Optional[Iterable[str]] = None,
        no_snapshot_groups: Optional[Iterable[str]] = None) -> None:
    """Snapshot the ``repo`` manifest file to the current state of the CLIP OS
    source tree."""

    # Locate the path to the manifest file with which repo has been
    # initialized:
    root_path = repo_root_path()
    try:
        internal_manifest_filepath = os.path.join(root_path, ".repo",
            os.readlink(os.path.join(root_path, ".repo/manifest.xml")))
    except:
        raise UnexpectedRepoSourceTreeStructure(line(
            """Could not locate the manifest file currently used by repo."""))

    # Compare the state of the "{repo}/.repo/manifests" and "{repo}/manifest/"
    # git repositories:
    try:
        internal_manifest_repo = git.Repo(os.path.join(root_path,
                                                       ".repo/manifests"))
    except:
        raise UnexpectedRepoSourceTreeStructure(line(
            """Could not identify "{repo}/.repo/manifests/" as a git
            repository."""))
    try:
        modifiable_manifest_repo = git.Repo(os.path.join(root_path,
                                                         "manifest"))
    except:
        raise UnexpectedRepoSourceTreeStructure(line(
            """Could not identify "{repo}/manifest/" as a git repository."""))
    if (internal_manifest_repo.head.commit !=
            modifiable_manifest_repo.head.commit):
        raise UnexpectedRepoSourceTreeStructure(line(
            """The current HEAD commits of the two git repositories
            "{repo}/.repo/manifests/" and "{repo}/manifest/" do not match."""))
    if internal_manifest_repo.is_dirty():
        raise UnexpectedRepoSourceTreeStructure(line(
            """The git repository in "{repo}/.repo/manifests/" is in a dirty
            state."""))
    if modifiable_manifest_repo.is_dirty():
        raise UnexpectedRepoSourceTreeStructure(line(
            """The git repository in "{repo}/manifest/" is in a dirty
            state."""))

    debug(line("""Repositories "{repo}/.repo/manifests/" and "{repo}/manifest/"
               are both in a clean state, on the same HEAD commit."""))

    internal_manifest_repo_path: str = internal_manifest_repo.working_dir
    internal_manifest_repo_filesubpath = os.path.relpath(
        internal_manifest_filepath, internal_manifest_repo_path)
    # Sanity check:
    if internal_manifest_repo_filesubpath.startswith(".."):
        raise UnexpectedRepoSourceTreeStructure(line(
            """The current manifest file in use by repo
            "{repo}/.repo/manifest.xml" is not a symlink to a file within
            "{repo}/.repo/manifests"."""))

    def _process(
            manifest_file_subpath: str,
            processed_manifests: Optional[Dict[str, ET.ElementTree]] = None
                ) -> Dict[str, ET.ElementTree]:
        """Process a manifest root file and keep an acumulator for recursion on
        ``<include>`` tags."""

        debug(line("""Processing manifest file {!r}""")
              .format(manifest_file_subpath))

        if not processed_manifests:
            processed_manifests = {}

        if (os.path.normpath(manifest_file_subpath) in
                processed_manifests.keys()):
            raise RepoSourceTreeManifestParsingError(line(
                """An already processed manifest file ({!r}) is again candidate
                to snapshot. Is there an include loop in the manifest file
                structure?""").format(manifest_file_subpath))

        try:
            parser = ET.XMLParser(target=CommentedTreeBuilder())
            xmldoc = ET.parse(os.path.join(internal_manifest_repo_path,
                                           manifest_file_subpath),
                              parser=parser)
        except Exception as exc:
            raise RepoSourceTreeManifestParsingError(line(
                """Failure when parsing {!r} manifest file. Exception raised
                was: {!r}""").format(manifest_file_subpath, exc))

        for proj in xmldoc.findall("./project"):
            try:
                proj_repo_subpath = proj.attrib["path"]
            except KeyError:
                raise UnexpectedRepoSourceTreeStructure(line(
                    """A project in manifest ({!r}) does not have a path.""")
                    .format(manifest_file_subpath))
            try:
                # according to repo manifest documentation, groups can be
                # separated with commas or spaces
                proj_group_set = set(proj.attrib["groups"]
                                         .replace(",", " ").split())
            except KeyError:
                proj_group_set = set()

            # skip this project if the project group set does not intersect
            # with the groups to snapshot set (if provided) or if it does
            # intersect with the groups NOT to snapshot set (if provided as
            # well):
            if snapshot_groups and not set(snapshot_groups) & proj_group_set:
                debug(line(
                    """Skipping project {!r} because it does not belong to any
                    group candidate for snapshot provided as argument.""")
                    .format(proj_repo_subpath))
                continue
            if (no_snapshot_groups and
                    set(no_snapshot_groups) & proj_group_set):
                debug(line(
                    """Skipping project {!r} because it belongs to a repo group
                    which shall not be snapshotted.""")
                    .format(proj_repo_subpath))
                continue

            try:
                proj_git_repo = git.Repo(os.path.join(root_path,
                                                      proj_repo_subpath))
            except:
                raise UnexpectedRepoSourceTreeStructure(line(
                    """Repo project {!r} is not a git repository anymore.""")
                    .format(proj_repo_subpath))

            if proj_git_repo.is_dirty():
                raise ProjectInRepoSourceTreeInUncleanState(line(
                    """Repo project {!r} is in a dirty state.""")
                    .format(proj_repo_subpath))

            if not proj_git_repo.head.is_valid():
                raise ProjectInRepoSourceTreeInUncleanState(line(
                    """Repo project {!r} has not a valid git HEAD.""")
                    .format(proj_repo_subpath))

            if use_branches:
                try:
                    proj_revision = proj_git_repo.head.reference.name
                except:
                    debug(line(
                        """Project {!r} cannot use git symbolic reference
                        because it is in a detached HEAD state.""")
                        .format(proj_repo_subpath))
                    proj_revision = proj_git_repo.head.commit.hexsha
            else:
                proj_revision = proj_git_repo.head.commit.hexsha

            # Check that the returned revision is effectively pointed by a Git
            # reference or any ancestor of a Git reference. This is required in
            # order to avoid using a Git revision that can be garbage-collected
            # by Git.
            # Important note: we do not check that the reference pointing on
            # the current HEAD is effectively valid on at least one Git remote.
            # We consider that it is up to the user to push that Git reference
            # to the suitable authoritative Git repostitory for future usage.
            for ref in proj_git_repo.references:
                if (proj_git_repo.head.commit == ref.commit or
                        proj_git_repo.head.commit in ref.commit.parents):
                    break
            else:
                raise ProjectInRepoSourceTreeInUncleanState(line(
                    """No Git symbolic reference is pointing to the current
                    HEAD commit of the project {!r} or any of its eventual
                    sucessors.""").format(proj_repo_subpath))

            # change the revision attribute in the XML project tag:
            proj.attrib["revision"] = proj_revision

            debug("Project {!r} will be snapshotted to revision {!r}.".format(
                    proj_repo_subpath, proj_revision))

        # manifest is processed: all the projects have been snapshotted to a
        # revision
        processed_manifests.update({
            os.path.normpath(manifest_file_subpath): xmldoc
        })

        # iterate with others manifests included
        for manifest in xmldoc.findall("./include"):
            manifest_subpath = manifest.attrib["name"]
            processed_manifests = _process(
                manifest_file_subpath=manifest_subpath,
                processed_manifests=processed_manifests
            )

        return processed_manifests

    processed_manifests = _process(
        manifest_file_subpath=internal_manifest_repo_filesubpath,
        processed_manifests={}
    )

    debug(line(
        """Manifest files successfully processed, proceeding to writing in
        "{repo}/manifest/" repository."""))

    modifiable_manifest_repo_path: str = modifiable_manifest_repo.working_dir
    for manifest_file_subpath, manifest_xmldoc in processed_manifests.items():
        manifest_file_path = os.path.join(modifiable_manifest_repo_path,
                                          manifest_file_subpath)
        manifest_xmldoc.write(manifest_file_path, encoding="UTF-8",
                              xml_declaration=True)
        # manually append a final newline since the write method above does
        # not do it:
        with open(manifest_file_path, "a") as fp:
            fp.write("\n")


class CommentedTreeBuilder(ET.TreeBuilder):
    """An :py:mod:`xml.etree.ElementTree.TreeBuilder` subclass that retains XML
    comments."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def comment(self, data: Union[bytes, Text]) -> None:
        # FIXME: Typing confusion ET.TreeBuilder.start and ET.TreeBuilder.end
        # take as first argument a Union[bytes, str] but ET.Comment is seen as
        # a Callable[[Union[str, str]], Element].
        # Awaiting proper fix or typing annotation fixing this issue:
        self.start(ET.Comment, {})  # type: ignore
        self.data(data)
        self.end(ET.Comment)  # type: ignore
