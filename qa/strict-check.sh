#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Check if in a virtualenv and that everything needed is available
if ! command -v cosmk &>/dev/null || [[ -z "${VIRTUAL_ENV:-}" ]]; then
    echo >&2 "\"cosmk\" could not be found in PATH or virtualenv not activated. Aborting."
    exit 1
fi

readonly REPOROOT="$(cosmk repo-root-path)"
if [[ -z "${REPOROOT}" || "$?" -ne 0 ]]; then
    echo >&2 "Could not get repo root path by using \"cosmk repo-root-path\"."
    exit 1
fi

echo >&2 "[pylint] Checking clipostoolkit package for errors (warnings dismissed)..."
"${VIRTUAL_ENV}/bin/pylint" \
    --rcfile "${REPOROOT}/toolkit/qa/pylintrc" \
    -E clipostoolkit

echo >&2
echo >&2 "===================================================================="
echo >&2

echo >&2 "[mypy] Checking types statically in clipostoolkit package..."
# HACK: mypy does not seem to locate packages installed as "editable" (i.e.
# installed with "setup.py develop" or with "pip install --editable").
# Therefore we need to help it by setting the path to the clipostoolkit package
# (actually the parent directory where the package dir can be found) in the
# variable MYPYPATH:
export MYPYPATH="${REPOROOT}/toolkit"
"${VIRTUAL_ENV}/bin/mypy" \
    --config-file "${REPOROOT}/toolkit/qa/mypy.ini" \
    --package clipostoolkit

# vim: set ts=4 sts=4 sw=4 et ft=sh:
