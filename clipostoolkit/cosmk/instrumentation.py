# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""Module handling product instrumentation logic."""

import os
import re
import sys
from enum import Enum
from typing import (Any, Dict, Iterable, MutableMapping, Optional, Text, Tuple,
                    Union, List)

import schema
import toml

from .commons import RECIPE_IDENTIFIER_RE, line
from .exceptions import (InstrumentationSpecificationError,
                         UnexpectedRepoSourceTreeStructure)
from .log import critical, debug, error, info, warn
from .sourcetree import repo_root_path


class Instrumentation(object):
    """Class describing the CLIP OS product (or derivative) instrumentation
    properties requested by the developer in the "instrumentation.toml" drop-in
    file at the root of the CLIP OS source tree."""

    SCHEMA = schema.Schema({
        "features": [schema.And(str, len)],
    })

    INSTRUMENTATION_FILEPATH = os.path.join(repo_root_path(),
                                            "instrumentation.toml")

    def __init__(self) -> None:
        self.__file_present = os.path.exists(self.INSTRUMENTATION_FILEPATH)
        if not self.__file_present:
            return

        try:
            with open(self.INSTRUMENTATION_FILEPATH, "r") as instru_fp:
                instru_data: MutableMapping[str, Any] = toml.load(instru_fp)
        except:
            raise InstrumentationSpecificationError(line(
                """Cannot open or parse as TOML the "instrumentation.toml" file
                placed at the root of the repo source tree."""))

        try:
            self.__instru = self.SCHEMA.validate(instru_data)
        except schema.SchemaError as exc:
            raise InstrumentationSpecificationError(line(
                """The "instrumentation.toml" file has an unexpected data
                structure. Reason: {!s}""").format(exc))

    @property
    def defined(self) -> bool:
        return bool(self.__file_present and self.__instru["features"])

    @property
    def features(self) -> Optional[List[str]]:
        if self.defined:
            features: List[str] = self.__instru['features']
            return features
        else:
            return None
