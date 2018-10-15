#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Get the basename of this program and the directory path to itself:
readonly PROGNAME="${BASH_SOURCE[0]##*/}"
readonly PROGPATH="$(realpath "${BASH_SOURCE[0]%/*}")"

# Full path to the venv and the vendor dirs:
readonly TOOLKIT="$(realpath "${PROGPATH}")"
readonly REPOROOT="$(realpath "${TOOLKIT}/..")"
readonly VENV="${REPOROOT}/run/toolkit"
readonly VENDOR="${REPOROOT}/assets/toolkit"
readonly REQUIREMENTS_TXT="${TOOLKIT}/requirements.txt"

# Check if not already in a virtualenv.
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo >&2 "Already in a virtualenv (\"${VIRTUAL_ENV:-}\"). Aborting."
    echo >&2 "Call \"deactivate\" shell function to properly exit this virtualenv."
    exit 1
fi

# This won't strip anything from an eventually previously set up virtualenv in
# this same directory.
mkdir -p "${VENV}"
python3 -m venv --symlinks "${VENV}"

# Avoid the message "You are using pip version X, however version Y is
# available.". We consider that we are always using a fairly recent version
# (although not the latest one) of pip brought by the Python package of the
# host Linux distribution.
cat <<EOF > "${VENV}/pip.conf"
[global]
    disable_pip_version_check = 1
EOF

# The reason why we use --index-url='' is to prevent pip from fetching packages
# (e.g. package dependencies) from PyPI automatically (and without our
# knowledge).
# In case of some missing dependencies, this will raise an error and will
# enable us to take action.
"${VENV}/bin/pip" install --index-url '' --find-links "file://${VENDOR}" \
    -r "${REQUIREMENTS_TXT}"

# Install the cosmk package in editable mode (aka. "setup.py develop" mode),
# i.e. without installing it with copies of all the Python files in the
# "site-packages" dir. This will allow us to work on the cosmk source code
# without having to constantly reinstall the package each time a change is made
# in this source code.
# Also, do not leave setuptools fetch and install dependencies (hence the
# "--no-deps" flag) for cosmk as we check them further down and we
# deliberatly trust the "requirements.txt" to include the dependencies for
# cosmk.
"${VENV}/bin/pip" install --no-deps --editable "${TOOLKIT}"

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
