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

echo >&2 "[pyflakes] Simple code analysis..."
"${VIRTUAL_ENV}/bin/pyflakes" "${REPOROOT}/toolkit/cosmk" || true

echo >&2
echo >&2 "===================================================================="
echo >&2

echo >&2 "[pylint] Code quality analysis (custom pylint configuration)..."
"${VIRTUAL_ENV}/bin/pylint" \
    --rcfile "${REPOROOT}/toolkit/qa/pylintrc" \
    --reports=yes cosmk || true

echo >&2
echo >&2 "===================================================================="
echo >&2

echo >&2 "[radon] Cyclomatic complexity report"
"${VIRTUAL_ENV}/bin/radon" cc --show-complexity --average \
    "${REPOROOT}/toolkit/cosmk"

echo >&2
echo >&2 "===================================================================="
echo >&2

echo >&2 "[radon] Maintanability index report"
"${VIRTUAL_ENV}/bin/radon" mi --show --sort "${REPOROOT}/toolkit/cosmk"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
