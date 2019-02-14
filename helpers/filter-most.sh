#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

set -e -u -o pipefail

readonly default="\e[0m"
readonly light_red="\e[91m"
readonly light_green="\e[92m"
readonly light_yellow="\e[93m"

filter_most() {
    # Filter repositories we usually don't want to touch with this command
    if [[  "${REPO_PATH}" = "ci/"*
        || "${REPO_PATH}" = "manifest"
        || "${REPO_PATH}" = "src/external/"*
        || "${REPO_PATH}" = "assets/"*
    ]]; then
        return
    fi
    printf "${light_yellow}>>${default} ${light_red}%-60.60s${default} | ${light_green}%s${default}\n" \
        "${REPO_PATH}" \
        "$(git rev-parse --abbrev-ref HEAD)"
    ${@}
    echo
}

if [[ -z "${REPO_PATH:-}" ]]; then
    echo "ERROR: Missing environment variables" >&2
    echo "This script must be run with: repo forall [projects...] -c $0 <command>" >&2
    exit 1
fi

filter_most ${@}

# vim: set ts=4 sts=4 sw=4 et ft=sh:
