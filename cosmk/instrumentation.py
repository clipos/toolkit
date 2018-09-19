# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

"""Module handling recipe instrumentation logic."""

import os
import re
import sys
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Text, Tuple, Union

import schema
import toml

from .commons import RECIPE_IDENTIFIER_RE, line
from .exceptions import (InstrumentationSpecificationError,
                         UnexpectedRepoSourceTreeStructure)
from .log import critical, debug, error, info, warn
from .sourcetree import repo_root_path


class InstrumentationLevel(Enum):
    """Instrumentation level enumeration for the recipes"""

    PRODUCTION = 0
    DEVELOPMENT = 1
    DEBUG = 2


def instrumented_recipes() -> Dict[str, InstrumentationLevel]:
    """Probes for existence of an "instrumentation.toml" drop-in file at the
    root of the `repo` source tree, parses this file and return a
    :py:data:`dict` of all the recipe identifiers (as keys) requested to be
    instrumented with their instrumentation level as value.

    :raise InstrumentationSpecificationError: in case of an incoherence in the
        ``instrumentation.toml`` file

    """

    instru_filepath = os.path.join(repo_root_path(), "instrumentation.toml")

    if not os.path.exists(instru_filepath):
        return dict()

    try:
        with open(instru_filepath, "r") as instru_fp:
            instru: Dict[str, Any] = toml.load(instru_fp)
    except:
        raise InstrumentationSpecificationError(line(
            """Cannot open or parse as TOML the "instrumentation.toml" file
            placed at the root of the repo source tree."""))

    instru_file_schema = schema.Schema({
        schema.Optional(level.name.lower(), default=[]): [
            schema.Regex(RECIPE_IDENTIFIER_RE.pattern)
        ] for level in InstrumentationLevel
    })

    try:
        instru = instru_file_schema.validate(instru)
    except schema.SchemaError as exc:
        raise InstrumentationSpecificationError(line(
            """The "instrumentation.toml" file has an unexpected data
            structure. Reason: {!s}""").format(exc))

    for level in InstrumentationLevel:
        for recipe in instru[level.name.lower()]:
            recipe_config_path = os.path.join(repo_root_path(), "products",
                                              recipe, "recipe.toml")
            if not os.path.exists(recipe_config_path):
                raise InstrumentationSpecificationError(line(
                    """The recipe {!r} is not a valid recipe or has no
                    configuration file in the products
                    folder.""").format(recipe))

    recipes: Dict[str, InstrumentationLevel] = dict()
    for level in InstrumentationLevel:
        for recipe_id in instru[level.name.lower()]:
            if recipe_id in recipes:
                raise InstrumentationSpecificationError(line(
                    """The recipe {!r} is specified more than once in the
                    "instrumentation.toml" file.""").format(recipe_id))
            recipes[recipe_id] = level

    return recipes
