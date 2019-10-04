#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

# Little foolproof check to avoid messing up the interactive shell of the
# inattentive user who does a "source toolkit/setup.sh" after a failed call to
# "source toolkit/activate" that invited him/her to call (but NOT sourced!)
# this present script before proceeding.
if [[ "${BASH_SOURCE[0]:-}" != "${0:-}" ]]; then
    echo >&2 "Warning! This script is not meant to be sourced. Call it normally like any other executable shell script."
    return 1
fi

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Get the basename of this program and the directory path to itself:
readonly PROGNAME="${BASH_SOURCE[0]##*/}"
readonly PROGPATH="$(realpath "${BASH_SOURCE[0]%/*}")"

# Full path to the venv and the vendor dirs:
readonly TOOLKIT="$(realpath "${PROGPATH}")"
readonly REPOROOT="$(realpath "${TOOLKIT}/..")"
readonly VENV="${REPOROOT}/run/venv"
readonly VENDOR="${REPOROOT}/assets/toolkit"
readonly REQUIREMENTS_TXT="${TOOLKIT}/requirements.txt"

# Check if not already in a virtualenv.
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo >&2 "Already in a virtualenv (\"${VIRTUAL_ENV:-}\"). Aborting."
    echo >&2 "Call \"deactivate\" shell function to properly exit this virtualenv."
    exit 1
fi

# Check if not running as root.
if [[ "$(id -u)" -eq 0 ]]; then
    echo >&2 "You should not be running this as root. Aborting."
    exit 1
fi

# Explicit check that we have Python 3.6 at least on this system. Otherwise,
# the use of the option "--prompt" will trigger an error that is absolutely not
# explicit to indicate that the Python version is too old (since "--prompt" has
# been introduced in Python 3.6).
# Note: 0 means true in Bash, but True is 1 in Python world. ;)
if python3 -c 'import sys; sys.exit(int(sys.version_info >= (3, 6)))'; then
    echo >&2 "Python 3.6 at least is required for the CLIP OS toolkit."
    exit 1
fi

# Create the virtualenv if it seems not to have been created succesfully
# previously:
if ! [[ -d "${VENV}" && -x "${VENV}/bin/pip" && -f "${VENV}/bin/activate" ]]; then
    mkdir -p "${VENV}"
    python3 -m venv --symlinks --prompt "toolkit" "${VENV}"
fi

# Populate the virtualenv with the set of packages we require and vendor:
#
# With the command above (python3 -m venv ...), we "inherit" by default 3
# Python packages from the user's Linux distro: setuptools, pip and wheel.
# (Notice that this is the normal behavior of the venv module in order to
# provide ways for the user to install new packages in its freshly created
# venv). However this behavior can cause potential issues that we do not want
# to hear about (since we do not control the versions of those distro-provided
# packages). But given the fact that we intentionally provide and vendor
# **ALL** the packages to be installed in the virtualenv (including pip,
# setuptools and wheel), we can trick pip into reinstalling them (including
# itself) with **OUR** packages provided and vendored (and with thoroughly
# pinned versions).
#
# The reason why we use --no-index is to prevent pip from fetching packages (or
# any package dependency) from PyPI automatically (and without our knowledge).
# In case of some missing dependencies, this will raise an error and will
# enable us to take action. With those options below, pip only consider the
# packages provided/vendored in $VENDOR, i.e. assets/toolkit (ensure to only
# gather sources packages in this directory).
"${VENV}/bin/pip" install \
    --no-index --find-links "file://${VENDOR}" \
    --no-cache-dir --no-binary :all: \
    --upgrade --force-reinstall setuptools pip wheel

# And then, we can proceed with the rest of the packages:
#
# [2019-04-02] Note/Hack: There is currently a bug in Pip 19 that prevent us
# from using the option "--no-binary :all:" with packages that make use of PEP
# 517 build system (e.g. flit), hence the "--no-use-pep517" flag below that
# will prevent Pip from trying to install such packages.
# This package restriction could be removed once the bug in Pip will be fixed,
# follow GitHub issue: https://github.com/pypa/pip/issues/6222
"${VENV}/bin/pip" install \
    --no-index --find-links "file://${VENDOR}" \
    --no-cache-dir --no-binary :all: \
    --no-use-pep517 \
    --upgrade -r "${REQUIREMENTS_TXT}"

# Install the clipostoolkit Python package in editable mode (aka. "setup.py
# develop" mode), i.e. without installing it with copies of all the Python
# files in the "site-packages" dir. This will allow us to work on the
# clipostoolkit package source code without having to constantly reinstall the
# package each time a change is made in this codebase.
# Also, do not leave setuptools fetch and install dependencies (hence the
# "--no-deps" flag) for clipostoolkit package as we check them further down and
# we deliberatly trust the "requirements.txt" to include explicitly all the
# dependencies for clipostoolkit package.
"${VENV}/bin/pip" install \
    --no-deps --no-index \
    --no-cache-dir --no-binary :all: \
    --editable "${TOOLKIT}"

# Symlink the helper scripts available in the toolkit's "helpers" directory in
# the "bin" directory of the virtualenv in order to make them appear via PATH.
# This eases the ability to call those scripts for the user (espcially for the
# scripts intended to be used with "repo forall" as repo changes the CWD).
for item in "${TOOLKIT}/helpers/"*; do
    if [[ -x "${item}" ]]; then
        # Assuming GNU coreutils for the "--relative-to" option of realpath:
        ln -snf \
            "$(realpath --relative-to="${VENV}/bin" "${item}")" \
            "${VENV}/bin/${item##*/}"
    fi
done
unset item

# Do not install just if the system provides it and we ask not to install it
if [[ ( -z "$(command -v just)" ) || ( -z "${CLIPOS_USE_SYSTEM_JUST+x}" ) ]]; then
    # Build and install just
    CARGO_HOME="${REPOROOT}/run/cargo"
    CARGO_TARGET_DIR="${REPOROOT}/run/cargo/target"

    mkdir -p "${CARGO_HOME}" "${CARGO_TARGET_DIR}"

    cat > "${CARGO_HOME}/config" <<EOF
[source.crates-io]
replace-with = "assets_crates-io"

[source.assets_crates-io]
local-registry = "${REPOROOT}/assets/crates-io"
EOF

    export CARGO_HOME
    export CARGO_TARGET_DIR

    cargo install --version "0.3.12" --root "${VENV}" --force just

    unset CARGO_HOME
    unset CARGO_TARGET_DIR
fi

# vim: set ts=4 sts=4 sw=4 et ft=sh tw=79:
