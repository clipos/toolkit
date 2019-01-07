#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# Setup script for cosmk

import codecs
import os
import re
import sys

from setuptools import setup

if not sys.version_info >= (3, 6):
    raise RuntimeError("cosmk package requires Python 3.6 or higher.")

# This current file:
here = os.path.abspath(os.path.dirname(__file__))

# Ugly functions that enable to have a single-source for the version string:
# See: https://packaging.python.org/guides/single-sourcing-package-version/
def read(*parts):
    with codecs.open(os.path.join(here, *parts), 'r') as fp:
        return fp.read()
def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

setup(
    name="cosmk",
    version=find_version("cosmk", "__init__.py"),
    description="The CLIP OS toolkit command line utility",
    url="https://www.clip-os.org/",
    author="ANSSI",
    author_email="clipos@ssi.gouv.fr",
    python_requires='>=3.6',
    packages=[
        "cosmk",
    ],
    package_data={
        "cosmk": [
            # Marker file labelling cosmk as inline type annotated (PEP 561)
            "py.typed",
        ]
    },
    zip_safe=False,  # required by mypy/py.typed/PEP 561
    # Dependencies required:
    install_requires=[
        "argcomplete",
        "libvirt-python",
        "GitPython",
        "psutil",
        "schema",
        "semver",
        "toml",
    ],
    extras_require={
        # Python quality assessment tools (static checkers, linter, etc.)
        "qa": [
            "mypy",
            "pylint",
            "radon",
        ],
        # Documentation building related packages
        "docs": [
            "sphinx",
            "sphinx-rtd-theme",
            "sphinx-autodoc-typehints",
        ],
    },
    entry_points={
        "console_scripts": [
            "cosmk=cosmk.__main__:main",
        ],
    },
)

# vim: set et ts=4 sts=4 sw=4:
