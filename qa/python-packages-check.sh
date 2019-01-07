#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Check if in a virtualenv and that everything needed is available
if ! command -v cosmk &>/dev/null || [[ -z "${VIRTUAL_ENV:-}" ]]; then
    echo >&2 "\"cosmk\" could not be found in PATH or virtualenv not activated. Aborting."
    exit 1
fi

echo >&2 "[pip] Checking that all the Python packages dependencies are satisfied..."
"${VIRTUAL_ENV}/bin/pip" check

# vim: set ts=4 sts=4 sw=4 et ft=sh:
