#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

set -e -u -o pipefail

readonly SELFNAME="${BASH_SOURCE[0]##*/}"
readonly SELFPATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

if [[ -z "${REPO_PATH:-}" ]]; then
    cat >&2 <<EOF
ERROR: Missing repo environment variables (REPO_*).

This script is intended to be run via the "repo forall" command, such as:

  $ repo forall [<project>...] -c '${0##*/} [<arg>...]'

Make sure to either use absolute paths for the command to launch or to have
activated the CLIP OS toolkit environment (see the "source_me.sh" file) to
expose the CLIP OS toolkit helper scripts in your PATH. This requirement is
explained by the fact that "repo forall" changes the current working directory
before invoking the specified command (commands are invoked from within each
repo project directory).

See "repo help forall" for more details. The above example is not exhaustive.
EOF
    exit 1
fi

main() {
    "${SELFPATH}/eval-annotations.sh" verify "$@"
}

main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
