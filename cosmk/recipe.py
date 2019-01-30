# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

"""The CLIP OS and derivatives recipe abstraction"""

import os
import re
from functools import partialmethod
from typing import Any, Dict, Type

import schema
import toml

from . import features  # for typing annotations and RecipeFeature subclasses
from .commons import (ENVVAR_FORMAT_RE, RECIPE_IDENTIFIER_RE, RECIPE_NAME_RE,
                      line)
from .exceptions import RecipeConfigurationError
from .instrumentation import InstrumentationLevel, instrumented_recipes
from .log import critical, debug, error, info, warn
from .product import Product
from .sourcetree import repo_root_path

# Typing annotations
# Disabled because mypy do not support yet recursive types :(
#RecipeConfig = Dict[str, 'RecipeConfigItem']
#RecipeConfigItem = Union[RecipeConfig, str, int, List[str], List[int]]
RecipeConfig = Dict[str, Any]
RecipeConfigItem = Any


class Recipe(object):
    """A CLIP OS toolkit recipe.

    :param identifier: the identifier of the recipe (*e.g.* ``clipos/core``)

    """

    def __init__(self, identifier: str) -> None:
        if not RECIPE_IDENTIFIER_RE.match(identifier):
            raise ValueError(
                "invalid identifier, must be \"<product>/<recipe>\"")
        self.identifier = identifier

        product_name, name = identifier.split("/")
        self.product = Product(product_name)
        if not RECIPE_NAME_RE.match(name):
            raise ValueError("invalid recipe name")
        self.name = name

        self.path = os.path.join(repo_root_path(), "products",
                                 self.product.name, self.name)
        self.config_path = os.path.join(self.path, "recipe.toml")
        if not os.path.exists(self.config_path):
            raise RecipeConfigurationError(
                "Cannot find a recipe configuration file for {!r} recipe."
                .format(self.name))

        debug("Parsing \"{}\"...".format(self.config_path))
        try:
            with open(self.config_path, "r") as conftoml:
                config = toml.load(conftoml)
        except:
            raise RecipeConfigurationError(
                "Cannot parse or open \"recipe.toml\" configuration file.")
        self.config = self.validate_metaconfig(config)

        # Recipe instrumentation level with fallback to production if not
        # defined:
        self.instrumentation_level: InstrumentationLevel = (
            instrumented_recipes().get(self.identifier,
                                       InstrumentationLevel.PRODUCTION))

        # initialize features for this recipe:
        self.features: Dict[str, 'features.RecipeFeature'] = {}
        self._featured_attrs: Dict[str, 'features.RecipeFeature'] = {}
        for feature_name in self.config["features"]:
            # get the RecipeFeature class corresponding to this feature name
            for feature_class in features.RecipeFeature.__subclasses__():
                if feature_class.NAME == feature_name:
                    break
            else:
                raise RecipeConfigurationError(line(
                    """could not find RecipeFeature for the feature name
                    {!r}""").format(feature_name))

            # initialize the recipe feature for this recipe
            feature = feature_class(recipe=self)
            # and validate the part of the recipe configuration that concerns
            # this feature (i.e. update config to ensure it matches this part
            # of schema):
            try:
                self.config = feature.SCHEMA.validate(self.config)
            except schema.SchemaError as exc:
                raise RecipeConfigurationError(line("""
                    Could not validate part of the data structure of the
                    "recipe.toml" configuration file relative to the recipe
                    feature {!r} that this recipe provides.
                    Reason below:""").format(self.__class__.__name__) +
                    "\n" + str(exc))
            # and set the featured attributes (can be methods or properties)
            # brought by this feature onto the attribute set of this recipe
            # object (without overwriting any pre-existent attribute):
            for featured_attr in feature.FEATURED_ATTRIBUTES:
                if not hasattr(self, featured_attr):
                    setattr(self, featured_attr,
                            getattr(feature, featured_attr))
                else:
                    raise RecipeConfigurationError(line(
                        """The feature {!r} comes overwriting an already
                        defined attribute for the recipe {!r}. Check that this
                        feature do not want to provide two incompatible
                        features.""").format(feature_name, self.identifier))
            # Keep the feature object in a property that can be handy and keep
            # also track of which feature has brought which attribute to this
            # object:
            self.features.update({feature_name: feature})
            self._featured_attrs.update(
                {attr: feature for attr in feature.FEATURED_ATTRIBUTES})

    @property
    def meta_schema(self) -> schema.Schema:
        """The schema for which the recipe configuration file (``recipe.toml``)
        needs to comply for common part (*i.e.* the part of the configuration
        common to all the recipes)"""

        return schema.Schema({
            "features": [
                schema.Or(*(featclass.NAME for featclass in
                            features.RecipeFeature.__subclasses__())),
            ],
            # All recipes have SDK except for SDK recipes
            schema.Optional("sdk"): schema.Regex(RECIPE_IDENTIFIER_RE.pattern),
            # other keys must be dict and will be validated by recipe features
            # validation methods
            str: dict,
        })

    def validate_metaconfig(self, config: RecipeConfig) -> RecipeConfig:
        """Validate the data structure of the recipe configuration file
        ("recipe.toml") which do not concern any feature implementation (*i.e.*
        the “meta” part of the recipe configuration).

        :param config: the configuration dict object to validate against the
            recipe meta schema

        :raise RecipeConfigurationError: in case of bad data structure

        """

        try:
            # Typing: schema is not type-annotated, therefore we manually
            # enforce type here for the return type.
            validated_conf: RecipeConfig = self.meta_schema.validate(config)
            return validated_conf
        except Exception as exc:
            raise RecipeConfigurationError(line("""
                Could not validate structure of "recipe.toml" configuration
                file. Reason below:""") + "\n"+ str(exc))

    @property
    def out_subpath(self) -> str:
        """Returns the output directory sub-path within the repo root."""
        return os.path.join("out", self.product.name, self.product.version,
                            self.name)

    @property
    def cache_subpath(self) -> str:
        """Returns the cache directory sub-path within the repo root."""
        return os.path.join("cache", self.product.name, self.product.version,
                            self.name)

    def __getattr__(self, name: str) -> None:
        """Attribute getter called when ``__getattribute__`` could not have
        found the attribute requested. This implementation is only for a
        convenience purpose to warn the user/developer that the current recipe
        does not provide the appropriate recipe feature that would have exposed
        this attribute."""

        compatible_features = []
        for featclass in features.RecipeFeature.__subclasses__():
            featname = featclass.NAME
            if name in featclass.FEATURED_ATTRIBUTES:
                compatible_features.append(featname)

        if compatible_features:
            hint_msg = " " + line(
                """This recipe may be missing a feature. Features providing
                attribute {!r} are the following: {feats}.""").format(
                    name, feats=", ".join(compatible_features))
        else:
            hint_msg = " No known recipe feature provide this attribute."

        raise AttributeError(
            "This recipe has no attrbute {!r}.".format(name) + hint_msg)
