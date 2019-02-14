#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Get the basename of this program and the directory path to itself:
readonly PROGNAME="${BASH_SOURCE[0]##*/}"
readonly PROGPATH="$(realpath "${BASH_SOURCE[0]%/*}")"

# Full path to the repo root dir:
readonly TOOLKIT="$(realpath "${PROGPATH}/..")"
readonly REPOROOT="$(realpath "${TOOLKIT}/..")"

# Full path to the venv and the vendor dirs:
readonly TMP_VENV="${REPOROOT}/run/venv_bump.tmp"
readonly VENDOR="$(realpath "${REPOROOT}/assets/toolkit")"

# Check if not already in a virtualenv.
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo >&2 "Already in a virtualenv (${VIRTUAL_ENV:-}). Aborting."
    exit 1
fi

destroy_tmp_venv() {
    rm -rf "${TMP_VENV}"
}
trap destroy_tmp_venv EXIT

echo >&2 "Creating a temporary virtualenv to get pip working."
destroy_tmp_venv
python3 -m venv --symlinks "${TMP_VENV}"

echo >&2 "Force to have to up-to-date pip in the virtualenv."
"${TMP_VENV}/bin/pip" install --no-cache --no-binary :all: --upgrade --force-reinstall pip

echo >&2 "Install the CLIP OS toolkit in that temporary virtualenv."
"${TMP_VENV}/bin/pip" install --no-cache --no-binary :all: --editable "${TOOLKIT}/.[qa,docs]"

echo >&2 "Generate the new \"requirements.txt\" by freezing the package list."
cat > "${TOOLKIT}/requirements.txt" <<END
# DO NOT EDIT THIS FILE BY HAND!
# This file was auto-generated by the script "${PROGNAME}"
# on $(date +'%Y-%m-%d at %H:%M:%S %Z').
#
# Note to Python developers:
# New dependencies to the CLIP OS toolkit/cosmk must be declared in the
# "setup.py" file either as a strict or extra dependency, not here.

END
# Do not forget '--all' to tell "pip freeze" to include setuptools, pip and all
# the other packages that are vital to pip. This requirements.txt will be
# complete and will enable us to use the option "--no-build-isolation" when
# re-installing all those pacakges without depending on an external Python
# packages index such as PyPI.
"${TMP_VENV}/bin/pip" freeze --all | sed -e '/^-e /d' >> "${TOOLKIT}/requirements.txt"

# Download from https://pypi.python.org/simple/ (the default) all the Python
# packages required for a usable development environment with cosmk:
mkdir -p "${VENDOR}"
# delete previous Python packages (keep hidden files and the README.md file):
shopt -s extglob nullglob
rm -f "${VENDOR}/"!(README.md)
shopt -u extglob nullglob
"${TMP_VENV}/bin/pip" download --no-binary ':all:' -d "${VENDOR}" \
    -r "${TOOLKIT}/requirements.txt"

echo >&2 "Python package dependencies and vendored packages both updated."

# vim: set ts=4 sts=4 sw=4 et ft=sh:
