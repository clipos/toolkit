# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""Auto-completion helpers to be used with argcomplete and argparse methods
within :mod:`cosmk.__main__`."""

import argparse
import glob
import os
from typing import Any, Callable, Iterable, List, Optional

import argcomplete

from .commons import line
from .features import RecipeFeature
from .product import Product
from .recipe import Recipe
from .sourcetree import repo_root_path


def features_for_action(action: str) -> List[str]:
    """Returns the list of recipe feature names which provide the given action
    name.

    :param action: the requested action name

    """

    feature_names = []
    for feat_class in RecipeFeature.__subclasses__():
        feat_name = feat_class.NAME
        if action in feat_class.FEATURED_ATTRIBUTES:
            feature_names.append(feat_name)

    return feature_names


def recipe_completer(prefix: str,
                     parsed_args: argparse.Namespace,
                     **kwargs: Any) -> Iterable[str]:
    """Returns a list of all the recipes available in the current repo source
    tree that would be appropriate regarding the current parsed arguments from
    the :py:func:`main()` function of ``cosmk``."""

    current_subcommand = parsed_args.subcommand
    try:
        # get the eligible features for the current action:
        eligible_features = features_for_action(current_subcommand)
    except Exception as exc:
        exctype = exc.__class__.__name__
        argcomplete.warn(line("""
            An exception {!r} occured when identifying the recipes features
            providing action {!r}""").format(exctype, current_subcommand))
    if not eligible_features:
        argcomplete.warn("No recipe feature provide action {!r}."
                         .format(current_subcommand))
        return []

    recipes = []
    recipe_globpat = os.path.join(repo_root_path(), "products", "*", "*")
    try:
        for recipe_path in glob.glob(recipe_globpat):
            if not os.path.isdir(recipe_path):
                continue
            _recipe_path_split = os.path.normpath(recipe_path).split("/")
            recipe = _recipe_path_split[-1]
            product = _recipe_path_split[-2]
            recipe_toml = os.path.join(recipe_path, "recipe.toml")
            if not os.path.exists(recipe_toml):
                continue
            try:
                recipe_identifier = "{}/{}".format(product, recipe)
                recipe_obj = Recipe(recipe_identifier)
            except Exception as exc:
                exctype = exc.__class__.__name__
                argcomplete.warn(line("""
                    An exception {!r} occured when evaluating recipe
                    {!r}.""").format(exctype, recipe_identifier))
                continue

            if set(eligible_features) & set(recipe_obj.features.keys()):
                recipes.append(recipe_identifier)

    except Exception as exc:
        exctype = exc.__class__.__name__
        argcomplete.warn(line("""
            An exception {!r} occured when enumerating all the available
            recipes.""").format(exctype))

    return recipes


def product_completer(prefix: str,
                      parsed_args: argparse.Namespace,
                      **kwargs: Any) -> Iterable[str]:
    """Returns a list of all the products available in the current repo source
    tree."""

    products = []
    product_globpat = os.path.join(repo_root_path(), "products", "*")
    try:
        for product_path in glob.glob(product_globpat):
            if not os.path.isdir(product_path):
                continue
            _product_path_split = os.path.normpath(product_path).split("/")
            product_name = _product_path_split[-1]
            try:
                product_obj = Product(product_name)
            except Exception as exc:
                exctype = exc.__class__.__name__
                argcomplete.warn(line("""
                    An exception {!r} occured when evaluating product
                    {!r}.""").format(exctype, product_name))
                continue
            products.append(product_name)
    except Exception as exc:
        exctype = exc.__class__.__name__
        argcomplete.warn(line("""
            An exception {!r} occured when enumerating all the available
            products.""").format(exctype))

    return products
