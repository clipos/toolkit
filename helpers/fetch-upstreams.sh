#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

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
    local return_status=0

    # ensure the remotes are properly declared according to the manifest file
    # at best, it ensure they are up-to-date by redeclaring them (it's cheap
    # anyway)
    "${SELFPATH}/eval-annotations.sh" declare-upstreams "$@"

    local remotes_str remotes
    remotes_str="$(git remote | awk '{printf $0" "}')"
    # use an array for homogeneity with the rest of the code
    read -ra remotes <<< "${remotes_str}"

    # getting the list of upstream remotes
    local remote upstream_remotes=()
    # shellcheck disable=SC2053
    for remote in "${remotes[@]}"; do
        if [[ "${remote}" =~ ^upstream[0-9]+$ ]]; then
            upstream_remotes+=("${remote}")
        fi
    done

    # and fetch those remotes
    local remote
    for remote in "${remotes[@]}"; do
        echo "[*] Fetching remote \"${remote}\"..."
        # The "--no-tags" option is there to prevent "git fetch" from fetching
        # the tags defined on the said remote, which is the default behavior
        # even if the tags are not requested in the refspecs for that remote.
        # Thus if we did not explicitely specify the tags refs (i.e.
        # "refs/tags/*") in the refspecs, the following command do not fetch
        # the tags.
        if git fetch --no-tags -- "${remote}"; then
            echo >&2 "[*] Remote \"${remote}\" successfully fetched for \"${REPO_PATH}\"."
        else
            echo >&2 "[!] Error has occured when fetching remote \"${remote}\" for \"${REPO_PATH}\" (\"git fetch\" returned $?)."
            return_status=1
            continue
        fi
    done

    return "${return_status}"
}

main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
