#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

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

# Explicit check that we have Python 3.6 at least on this system. Otherwise,
# the use of the option "--prompt" will trigger an error that is absolutely not
# explicit to indicate that the Python version is too old (since "--prompt" has
# been introduced in Python 3.6).
# Note: 0 means true in Bash, but True is 1 in Python world. ;)
if python3 -c 'import sys; sys.exit(int(sys.version_info >= (3, 6)))'; then
    echo >&2 "Python 3.6 at least is required for the CLIP OS toolkit."
    exit 1
fi

# This won't strip anything from an eventually previously set up virtualenv in
# this same directory.
mkdir -p "${VENV}"
python3 -m venv --symlinks --prompt "toolkit" "${VENV}"

# The reason why we use --no-index is to prevent pip from fetching packages (or
# any package dependency) from PyPI automatically (and without our knowledge).
# In case of some missing dependencies, this will raise an error and will
# enable us to take action.
# The "--no-build-isolation" enables to force reinstall setuptools and pip
# without them conflicting with each other (see
# https://pip.pypa.io/en/stable/reference/pip_install/#cmdoption-no-build-isolation
# and PEP 518).
"${VENV}/bin/pip" install --no-index --find-links "file://${VENDOR}" \
    --no-build-isolation -r "${REQUIREMENTS_TXT}"

# Install the cosmk package in editable mode (aka. "setup.py develop" mode),
# i.e. without installing it with copies of all the Python files in the
# "site-packages" dir. This will allow us to work on the cosmk source code
# without having to constantly reinstall the package each time a change is made
# in this source code.
# Also, do not leave setuptools fetch and install dependencies (hence the
# "--no-deps" flag) for cosmk as we check them further down and we
# deliberatly trust the "requirements.txt" to include the dependencies for
# cosmk.
"${VENV}/bin/pip" install --no-index --no-deps --editable "${TOOLKIT}"

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

# vim: set ts=4 sts=4 sw=4 et ft=sh:
