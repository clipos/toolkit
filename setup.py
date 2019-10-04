#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

# Setup script for the CLIP OS toolkit

import codecs
import os
import re
import sys

from setuptools import setup

if not sys.version_info >= (3, 6):
    raise RuntimeError("The CLIP OS toolkit requires Python 3.6 or higher.")

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
    name="CLIPOS_Toolkit",
    version=find_version("clipostoolkit", "__init__.py"),
    description="The CLIP OS toolkit",
    url="https://www.clip-os.org/",
    author="ANSSI",
    author_email="clipos@ssi.gouv.fr",
    python_requires='>=3.6',
    packages=[
        "clipostoolkit",
    ],
    package_data={
        "clipostoolkit": [
            # Marker file labelling clipostoolkit as inline type annotated (PEP 561)
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

            # Temporarily disabled because of the PEP 517 bug in Pip (radon has
            # transitive dependencies that only make use of PEP 517 packaging):
            #"radon",
        ],
    },
    entry_points={
        "console_scripts": [
            "cosmk=clipostoolkit.cosmk.__main__:main",
        ],
    },
)

# vim: set et ts=4 sts=4 sw=4:
