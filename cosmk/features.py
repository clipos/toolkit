# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

"""This module manages all the recipe features.

These recipe features act like traits for ``recipe.Recipe``'s."""

import abc
import os
import re
import signal
import shutil
from typing import Any, Dict, Optional, Set, Type

import schema

from . import recipe  # for typing annotations
from .commons import (ENVVAR_FORMAT_RE, RECIPE_IDENTIFIER_RE, is_tty_attached,
                      line)
from .exceptions import CosmkError, RecipeActionError
from .log import critical, debug, error, info, warn
from .privileges import ElevatedPrivileges
from .sdk import Sdk
from .sourcetree import repo_root_path
from .virt import VirtualizedEnvironment


class RecipeFeature(object, metaclass=abc.ABCMeta):
    """Recipe feature meta-class

    :param recipe: the recipe on which this feature applies

    :var NAME: the name of the feature that can be specified in the
        ``features`` list in the recipe configuration files to specify that a
        recipe implements this current feature
    :var FEATURED_ATTRIBUTES: the set of all the featured attributes provided
        to the :py:data:`Recipe` object by this recipe feature
    :var SCHEMA: the :py:data:`dict` schema for the recipe configuration part
        relative to the current feature

    .. note::
        This is a metaclass and therefore must not be used or initialized
        directly. Use a subclass of this metaclass.

    """

    NAME: str = "<meta-feature>"

    FEATURED_ATTRIBUTES: Set[str] = set()

    SCHEMA: schema.Schema = schema.Schema({})

    def __init__(self, recipe: 'recipe.Recipe') -> None:
        self.recipe = recipe

    def replace_placeholders(self, s: str, sdk_context: bool = False) -> str:
        """Replace the placeholders of a given string `s` and return a
        copy of this string."""

        repo_root = repo_root_path() if not sdk_context else "/mnt"
        # str.replace always returns a copy of the input string
        return (s.replace("{{repo}}", repo_root)
                 .replace("{{product}}", self.recipe.product.name)
                 .replace("{{version}}", self.recipe.product.version)
                 .replace("{{recipe}}", self.recipe.name))


class RecipeRootFeature(RecipeFeature):
    """Recipe feature for building rootfs from sources and binary packages"""

    NAME = "root"

    FEATURED_ATTRIBUTES = {"build", "image"}

    SCHEMA = schema.Schema({
        "root": {
            "sdk": schema.Regex(RECIPE_IDENTIFIER_RE.pattern),
            schema.Optional("env", default={}): {
                schema.Regex(ENVVAR_FORMAT_RE.pattern,
                             error="Bad environment variable name"): str
            },
            "build_steps": [str],
            "image_steps": schema.And([str], len),
        },
        str: object,  # do not consider other keys
    })

    def build(self,
              clear_cache: bool = False,
              clear_previous_build: bool = True) -> None:
        """Build a root tree for this recipe from sources and binary packages
        cache.

        :param clear_cache: whether or not the cache has to clear before
            processing root build
        :param clear_previous_build: whether or not the previous root build
            result has to be cleared

        """

        # using getattr to avoid static analyzers from complaining about
        # missing attr (but brought by a recipe feature):
        sdk = getattr(recipe.Recipe(self.recipe.config["root"]["sdk"]), "sdk")

        action_out_subpath = os.path.join(self.recipe.out_subpath, "build")
        action_out_path = os.path.join(repo_root_path(), action_out_subpath)

        # Clear out the previous image result when told so:
        if os.path.exists(action_out_path) and clear_previous_build:
            debug("clearing {!r}...".format(action_out_path))
            with ElevatedPrivileges():
                shutil.rmtree(action_out_path)

        # prepare output directory
        if not os.path.exists(action_out_path):
            os.makedirs(action_out_path)

        # hook the SDK container process to the current TTY (if existent):
        terminal = is_tty_attached()

        if clear_cache:
            debug("clearing cache for recipe {!r}...".format(
                self.recipe.identifier))
            with ElevatedPrivileges():
                shutil.rmtree(os.path.join(repo_root_path(),
                                           self.recipe.cache_subpath))

        with sdk.session(
                action_name="build",
                action_targeted_recipe=self.recipe,
                env={
                    key: self.replace_placeholders(value, sdk_context=True)
                    for key, value in self.recipe.config["root"]["env"].items()
                },
                terminal=terminal,
                shared_host_netns=True) as sess:
            for cmd in self.recipe.config["root"]["build_steps"]:
                info("{!r} builds recipe {!r}, runs:\n  {}".format(
                    sdk.recipe.identifier, self.recipe.identifier, cmd))
                sess.run(self.replace_placeholders(cmd, sdk_context=True))

    def image(self) -> None:
        """Build a root tree for this recipe only from binary packages cache
        and without any build-time dependency."""

        # using getattr to avoid static analyzers from complaining about
        # missing attr (but brought by a recipe feature):
        sdk = getattr(recipe.Recipe(self.recipe.config["root"]["sdk"]), "sdk")

        action_out_subpath = os.path.join(self.recipe.out_subpath, "image")
        action_out_path = os.path.join(repo_root_path(), action_out_subpath)

        # Always clear out the previous image result:
        if os.path.exists(action_out_path):
            debug("clearing {!r}...".format(action_out_path))
            with ElevatedPrivileges():
                shutil.rmtree(action_out_path)

        # prepare output directory
        os.makedirs(action_out_path)

        # hook the SDK container process to the current TTY (if existent):
        terminal = is_tty_attached()

        with sdk.session(
                action_name="image",
                action_targeted_recipe=self.recipe,
                env={
                    key: self.replace_placeholders(value, sdk_context=True)
                    for key, value in self.recipe.config["root"]["env"].items()
                },
                terminal=terminal,
                shared_host_netns=False) as sess:
            for cmd in self.recipe.config["root"]["image_steps"]:
                info("{!r} images recipe {!r}, runs:\n  {}".format(
                    sdk.recipe.identifier, self.recipe.identifier, cmd))
                sess.run(self.replace_placeholders(cmd, sdk_context=True))


class RecipeConfigureFeature(RecipeFeature):
    """Recipe feature for configuring root trees built during a recipe root
    feature"""

    NAME = "configure"

    FEATURED_ATTRIBUTES = {"configure"}

    SCHEMA = schema.Schema({
        "configure": {
            "sdk": schema.Regex(RECIPE_IDENTIFIER_RE.pattern),
            schema.Optional("env", default={}): {
                schema.Regex(ENVVAR_FORMAT_RE.pattern,
                             error="Bad environment variable name"): str
            },
            "root": schema.Regex(RECIPE_IDENTIFIER_RE.pattern),
            "steps": schema.And([str], len),
        },
        str: object,  # do not consider other keys
    })

    def configure(self) -> None:
        """TODO"""

        # using getattr to avoid static analyzers from complaining about
        # missing attr (but brought by a recipe feature):
        sdk = getattr(recipe.Recipe(self.recipe.config["configure"]["sdk"]),
                      "sdk")

        # the recipe to configure (i.e. what is the recipe for which we need to
        # get image-resulting root tree on which running the configuration
        # steps?):
        recipe_to_configure = recipe.Recipe(
            self.replace_placeholders(self.recipe.config["configure"]["root"]))

        # check that image action for the recipe designated by "root" has well
        # been run:
        image_out_subpath = os.path.join(recipe_to_configure.out_subpath,
                                         "image")
        image_out_path = os.path.join(repo_root_path(), image_out_subpath)
        if not os.path.exists(os.path.join(image_out_path, "root")):
            raise RecipeActionError(line("""
                Could not process a configure action step if the image action
                step from the recipe designated by "configure.root" has not
                been run before.
            """))

        action_out_subpath = os.path.join(self.recipe.out_subpath, "configure")
        action_out_path = os.path.join(repo_root_path(), action_out_subpath)

        # Always clear out the previous configure result:
        if os.path.exists(action_out_path):
            debug("clearing {!r}...".format(action_out_path))
            with ElevatedPrivileges():
                shutil.rmtree(action_out_path)

        # prepare output directory
        os.makedirs(action_out_path)

        # hook the SDK container process to the current TTY (if existent):
        terminal = is_tty_attached()

        # Retrieve the result of the image action to work on it for this
        # configuration step:
        with ElevatedPrivileges():
            debug(line(
                """copying resulting root of the image action step for the
                proper recipe ({!r}) into the working environment for the
                configure action step...""".format(
                    recipe_to_configure.identifier)))
            shutil.copytree(os.path.join(image_out_path, "root"),
                            os.path.join(action_out_path, "root"),
                            symlinks=True)

        with sdk.session(
                action_name="configure",
                action_targeted_recipe=self.recipe,
                env={
                    key: self.replace_placeholders(value, sdk_context=True)
                    for key, value in
                    self.recipe.config["configure"]["env"].items()
                },
                terminal=terminal,
                shared_host_netns=False) as sess:
            for cmd in self.recipe.config["configure"]["steps"]:
                info("{!r} configures recipe {!r}, runs:\n  {}".format(
                    sdk.recipe.identifier, self.recipe.identifier, cmd))
                sess.run(self.replace_placeholders(cmd, sdk_context=True))


class RecipeBundleFeature(RecipeFeature):
    """Recipe feature for bundling (*e.g.* making a tar archive or a squashfs
    image from any previous result of another recipe) whole or parts of the
    final recipe target."""

    NAME = "bundle"

    FEATURED_ATTRIBUTES = {"bundle"}

    SCHEMA = schema.Schema({
        "bundle": {
            "sdk": schema.Regex(RECIPE_IDENTIFIER_RE.pattern),
            schema.Optional("env", default={}): {
                schema.Regex(ENVVAR_FORMAT_RE.pattern,
                             error="Bad environment variable name"): str
            },
            "steps": schema.And([str], len),
        },
        str: object,  # do not consider other keys
    })

    def bundle(self) -> None:
        # using getattr to avoid static analyzers from complaining about
        # missing attr (but brought by a recipe feature):
        sdk = getattr(recipe.Recipe(self.recipe.config["bundle"]["sdk"]),
                      "sdk")

        action_out_subpath = os.path.join(self.recipe.out_subpath, "bundle")
        action_out_path = os.path.join(repo_root_path(), action_out_subpath)

        # Always clear out the previous image result:
        if os.path.exists(action_out_path):
            debug("clearing {!r}...".format(action_out_path))
            with ElevatedPrivileges():
                shutil.rmtree(action_out_path)

        # prepare output directory
        os.makedirs(action_out_path)

        # hook the SDK container process to the current TTY (if existent):
        terminal = is_tty_attached()

        with sdk.session(
                action_name="bundle",
                action_targeted_recipe=self.recipe,
                env={
                    key: self.replace_placeholders(value, sdk_context=True)
                    for key, value in self.recipe.config["bundle"]["env"].items()
                },
                terminal=terminal,
                shared_host_netns=False) as sess:
            for cmd in self.recipe.config["bundle"]["steps"]:
                info("{!r} bundles recipe {!r}, runs:\n  {}".format(
                    sdk.recipe.identifier, self.recipe.identifier, cmd))
                sess.run(self.replace_placeholders(cmd, sdk_context=True))


class RecipeSdkFeature(RecipeFeature):
    """Recipe feature for creating and proposing SDK objects to other
    features."""

    NAME = "sdk"

    FEATURED_ATTRIBUTES = {"bootstrap", "run", "sdk"}

    SCHEMA = schema.Schema({
        "runtime": {
            "additional_capabilities": [str],
            "additional_device_bindings": [str],
            "cwd": schema.And(str, len),
            "prelude_commands": [str],
            "postlude_commands": [str],
            schema.Optional("env", default={}): {
                schema.Regex(ENVVAR_FORMAT_RE.pattern,
                             error="Bad environment variable name"): str
            },
            "writable_assets_dirs_at_build": [schema.And(str, len)],
        },
        "bootstrap": {
            "rootfs_archive": str,
            schema.Optional("env", default={}): {
                schema.Regex(ENVVAR_FORMAT_RE.pattern,
                             error="Bad environment variable name"): str
            },
            "steps": [str],
        },
        "run": {
            schema.Optional("env", default={}): {
                schema.Regex(ENVVAR_FORMAT_RE.pattern,
                             error="Bad environment variable name"): str
            },
            "steps": schema.And([str], len),
        },
        str: object,  # do not consider other keys
    })

    def bootstrap(self) -> None:
        self.sdk.bootstrap(
            rootfs_archive=self.replace_placeholders(
                self.recipe.config["bootstrap"]["rootfs_archive"],
                sdk_context=False
            ),
            steps=[
                self.replace_placeholders(step, sdk_context=True)
                for step in self.recipe.config["bootstrap"]["steps"]
            ],
            env={
                key: self.replace_placeholders(value, sdk_context=True)
                for key, value in
                self.recipe.config["bootstrap"]["env"].items()
            },
        )

    def run(self) -> None:
        self.sdk.interactive_run(
            steps=[
                self.replace_placeholders(step, sdk_context=True)
                for step in self.recipe.config["run"]["steps"]
            ],
            env={
                key: self.replace_placeholders(value, sdk_context=True)
                for key, value in self.recipe.config["run"]["env"].items()
            },
        )

    @property
    def sdk(self) -> Sdk:
        return Sdk(
            recipe=self.recipe,
            cwd=self.replace_placeholders(
                self.recipe.config["runtime"]["cwd"],
                sdk_context=True
            ),
            env={
                key: self.replace_placeholders(value, sdk_context=True)
                for key, value in self.recipe.config["runtime"]["env"].items()
            },
            additional_capabilities=(
                self.recipe.config["runtime"]["additional_capabilities"]),
            additional_device_bindings=(
                self.recipe.config["runtime"]["additional_device_bindings"]),
            prelude_commands=[
                self.replace_placeholders(cmd, sdk_context=True)
                for cmd in self.recipe.config["runtime"]["prelude_commands"]
            ],
            postlude_commands=[
                self.replace_placeholders(cmd, sdk_context=True)
                for cmd in self.recipe.config["runtime"]["postlude_commands"]
            ],
            writable_assets_dirs_at_build=(
                self.recipe.config["runtime"]["writable_assets_dirs_at_build"])
        )


class RecipeVirtualizedEnvironmentFeature(RecipeFeature):
    """Recipe feature for creating, running and cleaning virtualized
    environment created from other recipe feature results."""

    NAME = "virt"

    FEATURED_ATTRIBUTES = {"spawn",  "create", "destroy"}

    SCHEMA = schema.Schema({
        "virt": {
            "xml_domain_template": schema.And(str, len),
            "xml_network_template": schema.And(str, len),
            "ovmf_code": schema.And(str, len),
            "ovmf_vars_template": schema.And(str, len),
            "qcow2_main_disk_image": schema.And(str, len),
        },
        str: object,  # do not consider other keys
    })

    @property
    def virtualized_environment(self) -> VirtualizedEnvironment:
        return VirtualizedEnvironment(
            name="{}-{}_{}".format(self.recipe.product.name,
                                   self.recipe.name,
                                   self.recipe.product.tainted_version),
            libvirt_domain_xml_template=self.replace_placeholders(
                self.recipe.config["virt"]["xml_domain_template"],
                sdk_context=False),
            libvirt_network_xml_template=self.replace_placeholders(
                self.recipe.config["virt"]["xml_network_template"],
                sdk_context=False),
            qcow2_main_disk_image=self.replace_placeholders(
                self.recipe.config["virt"]["qcow2_main_disk_image"],
                sdk_context=False),
            ovmf_firmware_code=self.replace_placeholders(
                self.recipe.config["virt"]["ovmf_code"],
                sdk_context=False),
            ovmf_firmware_vars_template=self.replace_placeholders(
                self.recipe.config["virt"]["ovmf_vars_template"],
                sdk_context=False),
        )

    def spawn(self,
              destroy_preexisting: bool = False,
              spawn_virt_manager_console: bool = True) -> None:
        virtenv = self.virtualized_environment
        virtenv.create(start=True, destroy_preexisting=destroy_preexisting)
        if spawn_virt_manager_console:
            info(line("""Spawning graphical virtual machine manager
                      (\"virt-manager\")..."""))
            virtenv.spawn_virt_manager_console()
        try:
            info("Interrupt the virtual machine with Control+C (SIGINT).\n" +
                 line("""Note: this will kill the virtual machine and cleanup
                      the libvirt domain and its associated virtual
                      network."""))
            signal.pause()
        except KeyboardInterrupt:
            virtenv.destroy()

    def create(self,
               destroy_preexisting: bool = False,
               spawn_virt_manager_console: bool = False) -> None:
        virtenv = self.virtualized_environment
        virtenv.create(start=False, destroy_preexisting=destroy_preexisting)
        if spawn_virt_manager_console:
            info(line(
                """Spawning graphical virtual machine manager
                (\"virt-manager\")..."""))
            virtenv.spawn_virt_manager_console()

    def destroy(self) -> None:
        virtenv = self.virtualized_environment
        virtenv.destroy()


class RecipeSignatureFeature(RecipeFeature):
    """Recipe feature for XXX"""

    NAME = "sign"
