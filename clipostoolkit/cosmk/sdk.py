# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""CLIP OS toolkit SDK class"""

import contextlib
import os
import shlex
import shutil
import sys
import tarfile
import tempfile
from typing import Dict, Iterator, List, Optional, Tuple

import schema

from . import recipe  # for typing annotations
from .commons import ENVVAR_FORMAT_RE, is_tty_attached
from .container import (Container, ContainerDeviceBinding, ContainerMountpoint,
                        ContainerSession)
from .exceptions import (CosmkError, SdkBootstrapError, SdkError,
                         SdkNotFoundError)
from .fs import mksquashfs
from .log import critical, debug, error, info, warn
from .privileges import ElevatedPrivileges
from .sourcetree import repo_root_path


class Sdk(object):
    """A CLIP OS toolkit SDK"""

    def __init__(self,
                 recipe: 'recipe.Recipe',
                 cwd: str = "/",
                 env: Optional[Dict[str, str]] = None,
                 additional_capabilities: Optional[List[str]] = None,
                 additional_device_bindings: Optional[List[str]] = None,
                 prelude_commands: Optional[List[str]] = None,
                 postlude_commands: Optional[List[str]] = None,
                 writable_assets_dirs_at_build: Optional[List[str]] = None
                ) -> None:
        self.recipe = recipe
        self.additional_capabilities = additional_capabilities
        self.additional_device_bindings = additional_device_bindings
        self.cwd = cwd
        self.env = env
        self.prelude_commands = prelude_commands if prelude_commands else []
        self.postlude_commands = postlude_commands if postlude_commands else []
        self.writable_assets_dirs_at_build = writable_assets_dirs_at_build


    def container_mountpoints(self,
                              action_name: str,
                              action_targeted_recipe: 'recipe.Recipe',
                              writable_repo_root: bool = False
                             ) -> List[ContainerMountpoint]:
        """Returns the list of ``ContainerMountpoint``'s corresponding to the
        mountpoints of the SDK context."""

        mntpoints = [
            ContainerMountpoint(
                source=repo_root_path(),
                target="/mnt",
                options=["bind", "rw" if writable_repo_root else "ro"],
            )
        ]

        if not writable_repo_root:
            # Identify the repo sub-path for the output directory relative to
            # the current recipe action and create it if not existing:
            out_subpath_for_action = os.path.join(
                action_targeted_recipe.out_subpath, action_name)
            if not os.path.exists(os.path.join(repo_root_path(),
                                               out_subpath_for_action)):
                os.makedirs(os.path.join(repo_root_path(),
                                         out_subpath_for_action))

            # Same for the cache subpath & package cache subpath:
            cache_subpath = action_targeted_recipe.cache_subpath
            cache_subpath_for_action = os.path.join(cache_subpath, action_name)
            cache_subpath_for_packages = os.path.join(cache_subpath, "binpkgs")
            if not os.path.exists(os.path.join(repo_root_path(),
                                               cache_subpath_for_action)):
                os.makedirs(os.path.join(repo_root_path(),
                                         cache_subpath_for_action))
            if not os.path.exists(os.path.join(repo_root_path(),
                                               cache_subpath_for_packages)):
                os.makedirs(os.path.join(repo_root_path(),
                                         cache_subpath_for_packages))

            # Always mount output & cache path for current action read-write.
            mntpoints += [
                ContainerMountpoint(
                    source=os.path.join(repo_root_path(),
                                        out_subpath_for_action),
                    target=os.path.join("/mnt", out_subpath_for_action),
                    options=["bind", "rw"],
                ),
                ContainerMountpoint(
                    source=os.path.join(repo_root_path(),
                                        cache_subpath_for_action),
                    target=os.path.join("/mnt", cache_subpath_for_action),
                    options=["bind", "rw"],
                )
            ]

            if action_name == "bootstrap" or action_name == "build":
                # Only build and bootstrap actions need read-write access to
                # the package cache.
                mntpoints += [
                    ContainerMountpoint(
                        source=os.path.join(repo_root_path(), cache_subpath_for_packages),
                        target=os.path.join("/mnt", cache_subpath_for_packages),
                        options=["bind", "rw"],
                    )
                ]

                # Build and bootstrap actions may download assets
                if self.writable_assets_dirs_at_build:
                    for asset_dir in self.writable_assets_dirs_at_build:
                        subpath = os.path.join("assets", asset_dir)
                        mntpoints += [
                            ContainerMountpoint(
                                source=os.path.join(repo_root_path(), subpath),
                                target=os.path.join("/mnt", subpath),
                                options=["bind", "rw"],
                            )
                        ]

        # There is a long-known bug between OverlayFS and GNU tar (see:
        # https://github.com/coreos/bugs/issues/1095) that make GNU tar fail
        # with an error "Directory renamed before its status could be
        # extracted". However, Portage works a lot with GNU tar for its creation
        # and extraction of binary packages, especially in /var/tmp and this
        # directory actually sits on top of the overlayfs container mountpoint
        # that constitutes the root filesystem of the container. Hence the bug
        # previously mentioned can affect us.
        # Therefore we decide not to rely on the fact that the upperdir of the
        # rootfs of the container is a tmpfs for both /tmp and /var/tmp (in the
        # container) and we mount those points as normal tmpfs mountpoints:
        mntpoints += [
            ContainerMountpoint(
                source="tmpfs",
                target="/tmp",
                type="tmpfs",
                options=["nodev", "nosuid"],
            ),
            ContainerMountpoint(
                source="tmpfs",
                target="/var/tmp",
                type="tmpfs",
                options=[],  # no mount options for Portage
            ),
        ]

        return mntpoints

    def bootstrap(self,
                  rootfs_archive: str,
                  steps: Optional[List[str]] = None,
                  env: Optional[Dict[str, str]] = None) -> None:
        """Bootstrap a SDK from the rootfs archive file specified in the recipe
        configuration file with the suitable script in order to produce a
        squashfs image that can be run as a container with the ``Container``
        class."""

        # create output directory to store temporary SDK squashfs images.
        output_path = os.path.join(repo_root_path(), self.recipe.out_subpath)
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # prepare the output directory where to store the resulting squashfs
        # image of this bootstrapped SDK
        cache_path = os.path.join(repo_root_path(), self.recipe.cache_subpath)
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        squashfs_path = os.path.join(cache_path, "rootfs.squashfs")

        # hook the SDK container process to the current TTY (if existent):
        terminal = is_tty_attached()

        # lets work in a temporary dedicated directory in order to extract the
        # archive file and transform it into a squashfs image to be able to
        # spawn a container from it and call the bootstrap script from within:
        tempdir_base = os.path.join(repo_root_path(), "run", "tmp")
        if not os.path.exists(tempdir_base):
            os.makedirs(tempdir_base)

        tmp_bootstrap_dir = tempfile.TemporaryDirectory(
            dir=tempdir_base,
            prefix=("bootstrap-{product}-{recipe}.".format(
                        product=self.recipe.product.name,
                        recipe=self.recipe.name)))

        with tmp_bootstrap_dir as tmpdir:
            #
            # Step 1: extract the tar archive file and make it a squashfs image
            # file to be used to spawn a first container.
            #
            tarimage_contents_path = os.path.join(tmpdir, "tar-contents")
            os.mkdir(tarimage_contents_path)

            # Since the temporary bootstrap dir (`tmpdir`) has been created
            # without elevated privileges and since the tar-contents directory
            # contains root-owned files, we need to wipe this directory with
            # elevated privileges (otherwise an EPERM error will be raised when
            # exiting the context manager tmp_bootstrap_dir):
            try:
                with ElevatedPrivileges(), \
                        tarfile.open(rootfs_archive, "r:*") as tar:
                    # Important: ensure to keep ownership with
                    # `numeric_owner=True`
                    # Important note regarding the encoding used in the tar
                    # archives (FIXME?): An exception can be raised when the
                    # encoding of the tar archive does not match the system
                    # encoding. This exception can be confusing by its nature
                    # but is well documented and understandable, see the Python
                    # documentation for the "tarfile" module, on section
                    # "Unicode issues".
                    tar.extractall(path=tarimage_contents_path,
                                   numeric_owner=True)

                tmp_bootstrap_squashfs_path = os.path.join(
                    tmpdir, "to-bootstrap.squashfs")
                with ElevatedPrivileges() as unprivileged_uid_gid:
                    mksquashfs(tmp_bootstrap_squashfs_path,
                               tarimage_contents_path,
                               store_xattrs=True,
                               detect_sparse_files=True,
                               find_duplicates=True)
                    uid, gid = unprivileged_uid_gid
                    os.chown(tmp_bootstrap_squashfs_path, uid, gid)
            finally:
                with ElevatedPrivileges():
                    shutil.rmtree(tarimage_contents_path)

            #
            # Step 2: invoke the bootstrap script from within a container
            # created from the squashfs file above
            #
            bootstrap_cont = Container(
                name=("bootstrap-{product}-{recipe}.".format(
                        product=self.recipe.product.name,
                        recipe=self.recipe.name)),
                rootfs=tmp_bootstrap_squashfs_path,
                shared_host_netns=True
            )
            if self.additional_capabilities:
                bootstrap_cont.capabilities.update(
                    set(self.additional_capabilities))
            bootstrap_cont.additional_mountpoints = self.container_mountpoints(
                action_name="bootstrap",
                action_targeted_recipe=self.recipe
            )
            if self.additional_device_bindings:
                bootstrap_cont.device_bindings.extend([
                    ContainerDeviceBinding(dev) for dev in
                    self.additional_device_bindings
                ])
            cwd = self.cwd
            bootstrap_env = env if env else {} # rename env arg for consistency
            env = self.env.copy() if self.env else {}
            env.update(bootstrap_env)
            env.update({
                "CURRENT_PRODUCT": self.recipe.product.name,
                "CURRENT_PRODUCT_VERSION": self.recipe.product.version,
                "CURRENT_PRODUCT_TAINTED_VERSION":
                    self.recipe.product.tainted_version,
                "CURRENT_RECIPE": self.recipe.name,
                "CURRENT_RECIPE_INSTRUMENTATION_LEVEL":
                    self.recipe.instrumentation_level.value,
                "CURRENT_ACTION": "bootstrap",
                "CURRENT_SDK_PRODUCT": self.recipe.product.name,
                "CURRENT_SDK_RECIPE": self.recipe.name,
            })
            propkeys_ordered_list = []
            for idx, key in enumerate(self.recipe.product.properties):
                propkeys_ordered_list.append(key)
                env.update({
                    "CURRENT_PRODUCT_PROPERTY_{}".format(idx):
                        self.recipe.product.properties[key],
                })
            env.update({
                "CURRENT_PRODUCT_PROPERTIES": " ".join(propkeys_ordered_list),
            })
            with ElevatedPrivileges() as unprivileged_uid_gid, \
                    bootstrap_cont.session() as sess:
                # write a file named ".sdk" at the root of the filesystem to
                # serve as an SDK indicator for some scripts
                sess.run(command=["sh", "-c", "> /.sdk"], cwd=cwd, env=env,
                         terminal=terminal)

                for cmd in self.prelude_commands:
                    debug("running prelude for SDK {!r}:\n  {}".format(
                        self.recipe.identifier, cmd))
                    sess.run(command=shlex.split(cmd), cwd=cwd, env=env,
                             terminal=terminal)

                # No bootstrapping steps is a legitimate case, where the
                # bootstrap rootfs archive provided already has everything
                # prepared, thus requiring no specific bootstrapping command to
                # be run to produce the SDK rootfs image.
                if steps:
                    for cmd in steps:
                        info("bootstrapping SDK recipe {!r}, running:\n  {}"
                                .format(self.recipe.identifier, cmd))
                        sess.run(command=shlex.split(cmd), cwd=cwd, env=env,
                                terminal=terminal)

                for cmd in self.postlude_commands:
                    debug("running postlude for SDK {!r}:\n  {}".format(
                        self.recipe.identifier, cmd))
                    sess.run(command=shlex.split(cmd), cwd=cwd, env=env,
                             terminal=terminal)

                # Snapshot the container rootfs into the resulting SDK squashfs
                # image:
                sess.snapshot(squashfs_path)
                uid, gid = unprivileged_uid_gid
                os.chown(squashfs_path, uid, gid)

    def interactive_run(self,
                        recipe: 'recipe.Recipe',
                        command: Optional[str] = None,
                        env: Optional[Dict[str, str]] = None,
                        shared_host_netns: bool = True,
                        writable_repo_root: bool = True) -> None:
        """Run a command interactively in this SDK, in the given recipe
        context"""

        if not command:
            if not is_tty_attached():
                raise CosmkError(
                    "not connected to a tty, cannot run a SDK interactively")

            # Interactive Bash shell as login shell (in order to source
            # /etc/profile):
            command = "bash -li"

        with self.session(action_name="run",
                          action_targeted_recipe=recipe,
                          writable_repo_root=writable_repo_root,
                          terminal=True,
                          env=env,
                          shared_host_netns=shared_host_netns) as sdk_sess:
            info("Running in {!r} with recipe {!r}: {}"
                .format(self.recipe.identifier, recipe.identifier, command))
            sdk_sess.run(command)

    @contextlib.contextmanager
    def session(self,
                action_name: str,
                action_targeted_recipe: 'recipe.Recipe',
                writable_repo_root: bool = False,
                terminal: bool = False,
                env: Optional[Dict[str, str]] = None,
                shared_host_netns: bool = False) -> Iterator["SdkSession"]:
        """Creates an SDK session from this SDK recipe in order to be able to
        spawn the appropriate container (*i.e.* for treating a given `action`
        for a given `recipe` of the product `product`) and pass commands to it.

        This context manager is in charge of creating the container (in the
        sense of the ``Container`` class) for the living time span of the
        context manager.

        """

        sdk_rootfs_path = os.path.join(repo_root_path(),
                                       self.recipe.cache_subpath,
                                       "rootfs.squashfs")
        if not os.path.exists(sdk_rootfs_path):
            raise SdkNotFoundError("could not found rootfs squashfs image "
                                   "file for this SDK")

        sdk_container = Container(
            name="{sdkproduct}-{sdk}.{action}.{product}-{recipe}".format(
                sdkproduct=self.recipe.product.name,
                sdk=self.recipe.name,
                action=action_name,
                product=action_targeted_recipe.product.name,
                recipe=action_targeted_recipe.name
            ),
            rootfs=sdk_rootfs_path,
            shared_host_netns=shared_host_netns
        )
        if self.additional_capabilities:
            sdk_container.capabilities.update(
                set(self.additional_capabilities))
        sdk_container.additional_mountpoints = self.container_mountpoints(
            action_name=action_name,
            action_targeted_recipe=action_targeted_recipe,
            writable_repo_root=writable_repo_root
        )
        if self.additional_device_bindings:
            sdk_container.device_bindings.extend([
                ContainerDeviceBinding(dev) for dev in
                self.additional_device_bindings
            ])
        cwd = self.cwd
        overloaded_env = env if env else {} # rename env arg for consistency
        env = self.env.copy() if self.env else {}
        env.update(overloaded_env)
        env.update({
            "CURRENT_PRODUCT": action_targeted_recipe.product.name,
            "CURRENT_PRODUCT_VERSION": action_targeted_recipe.product.version,
            "CURRENT_PRODUCT_TAINTED_VERSION":
                action_targeted_recipe.product.tainted_version,
            "CURRENT_RECIPE": action_targeted_recipe.name,
            "CURRENT_RECIPE_INSTRUMENTATION_LEVEL":
                action_targeted_recipe.instrumentation_level.value,
            "CURRENT_ACTION": action_name,
            "CURRENT_SDK_PRODUCT": self.recipe.product.name,
            "CURRENT_SDK_RECIPE": self.recipe.name,
        })
        propkeys_ordered_list = []
        for idx, key in enumerate(action_targeted_recipe.product.properties):
            propkeys_ordered_list.append(key)
            env.update({
                "CURRENT_PRODUCT_PROPERTY_{}".format(idx):
                    action_targeted_recipe.product.properties[key],
            })
        env.update({
            "CURRENT_PRODUCT_PROPERTIES": " ".join(propkeys_ordered_list),
        })
        with ElevatedPrivileges(), sdk_container.session() as cont_sess:
            for cmd in self.prelude_commands:
                debug("running prelude for SDK {!r}:\n  {}".format(
                    self.recipe.identifier, cmd))
                cont_sess.run(command=shlex.split(cmd), cwd=cwd, env=env,
                              terminal=terminal)

            yield SdkSession(container_session=cont_sess,
                             cwd=cwd,
                             env=env,
                             terminal=terminal)

            for cmd in self.postlude_commands:
                debug("running postlude for SDK {!r}:\n  {}".format(
                    self.recipe.identifier, cmd))
                cont_sess.run(command=shlex.split(cmd), cwd=cwd, env=env,
                              terminal=terminal)

class SdkSession(object):
    """Session of a SDK container."""

    def __init__(self,
                 container_session: ContainerSession,
                 cwd: str,
                 env: Dict[str, str],
                 terminal: bool = False) -> None:
        self.container_session = container_session
        self.cwd = cwd
        self.env = env
        self.terminal = terminal

    def run(self, command: str) -> None:
        """Run a command in this SDK container session."""

        self.container_session.run(
            command=shlex.split(command),
            cwd=self.cwd,
            env=self.env,
            terminal=self.terminal,
        )
