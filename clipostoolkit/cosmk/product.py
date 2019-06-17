# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""Module for products manageable with cosmk"""

import os
import re
from typing import Any, Dict, Iterator, MutableMapping, Optional, Tuple

import schema
import semver
import toml

from .commons import PRODUCT_NAME_RE, line
from .exceptions import ProductPropertiesError
from .instrumentation import Instrumentation
from .log import critical, debug, error, info, warn
from .sourcetree import repo_root_path

# Typing annotations
ProductProperties = Dict[str, str]


class Product(object):
    """Class describing a CLIP OS (or one of its derivative) product.

    :param name: the name of the product (*e.g.* ``clipos``)

    """

    SCHEMA = schema.Schema({
        # Version is the only mandatory property for a product.
        "version": schema.And(str, len, semver.parse),
        # Everything else is dependent of the recipe scripts implementation:
        str: object  # ignore the rest
    })

    def __init__(self, name: str) -> None:
        if not PRODUCT_NAME_RE.match(name):
            raise ValueError("invalid product name")
        self.name = name

        self.path = os.path.join(repo_root_path(), "products", self.name)
        self.properties_path = os.path.join(self.path, "properties.toml")
        if not os.path.exists(self.properties_path):
            raise ProductPropertiesError(
                "Cannot find a product properties file for {!r} product."
                .format(self.name))
        debug("Parsing {!r}...".format(self.properties_path))
        try:
            with open(self.properties_path, "r") as proptoml:
                prop_dict: MutableMapping[str, Any] = toml.load(proptoml)
        except:
            raise ProductPropertiesError(
                "Cannot parse or open \"properties.toml\" properties file.")
        self.properties = self.validate_properties(prop_dict)

    @property
    def version(self) -> str:
        """Returns the version of this product as defined in its
        "properties.toml" file."""
        return self.properties["version"]

    @property
    def tainted_version(self) -> str:
        """Returns the version of this product as defined in its
        "properties.toml" file but "tainted" with a build flag
        ``instrumentation`` if at least one instrumentation feature is
        enabled."""

        version = semver.parse(self.version)
        def taint_version(tag: str) -> None:
            if version["build"]:
                version["build"] += "." + tag
            else:
                version["build"] = tag

        instru = Instrumentation()
        if instru.features:
            taint_version("instrumented")

        return str(semver.VersionInfo(**version))

    def validate_properties(self,
                            prop_dict: MutableMapping[str, Any],
                           ) -> ProductProperties:
        """Validate the data structure of the product properties file
        ("properties.toml") and reorganize them into a "flattened"
        :py:data:`dict`.

        :param prop_dict: the properties dict object to validate against the
            schema (:py:data:`SCHEMA`)

        :raise ProductPropertiesError: in case of bad data structure

        """

        try:
            # Typing: schema is not type-annotated, therefore we manually
            # enforce type here for the return type.
            validated_props: Dict[str, Any] = self.SCHEMA.validate(prop_dict)
        except Exception as exc:
            raise ProductPropertiesError(line(
                """Could not validate structure of "properties.toml" file for
                the product {!r}. Reason: {!s}""").format(self.name, exc))

        # Since schema is not capable of doing recursive dict schema
        # validation, let's make the validation ourselves to ensure all the
        # keys have a serializable format and hold as values either strings or
        # other dicts of properties:
        key_format_re = re.compile(r'^[a-zA-Z0-9_]+$')
        def walk(props: Dict[str, Any],
                 prefix: Optional[str] = None) -> Iterator[Tuple[str, str]]:
            for key, val in props.items():
                if not isinstance(key, str):
                    raise ProductPropertiesError(line(
                        """Key {!r} not of type string in properties file of
                        product {!r}.""").format(key, self.name))
                if not key_format_re.match(key):
                    raise ProductPropertiesError(line(
                        """Key {!r} in properties file of product {!r} is
                        invalid (keys must match regular expression {!r}).""")
                        .format(key, self.name, key_format_re.pattern))
                if isinstance(val, str):
                    yield ("{}.{}".format(prefix, key) if prefix else key), val
                elif isinstance(val, dict):
                    # recurse and yield
                    for k, v in walk(val, ("{}.{}".format(prefix, key)
                                           if prefix else key)):
                        yield k, v

                else:
                    raise ProductPropertiesError(line(
                        """The key {!r} in the properties file of the product
                        {!r} holds a value which is not a string. Only strings
                        can be serialized to SDK scripts.""")
                        .format(
                            ("{}.{}".format(prefix, key) if prefix else key),
                            self.name))

        # Flatten the nested dict into a one-level dict:
        return dict(walk(validated_props))
