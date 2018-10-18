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

    # This is the remote name declared in the manifest file for the current
    # project/repository:
    local default_remote="${REPO_REMOTE}"

    # Query Git to retrieve all the available refs into an array
    local all_refs_str all_refs
    all_refs_str="$(git show-ref | awk '{ printf $2" "}')"
    # use an array for homogeneity with the rest of the code
    read -ra all_refs <<< "${all_refs_str}"

    # Retrieve the names of the branches defined in the default remote from the
    # refs/remotes/* references (this is done automatically by Git and is the
    # default behavior):
    local branch_names_to_yield=()
    local ref
    for ref in "${all_refs[@]}"; do
        if [[ "${ref}" =~ ^"refs/remotes/${default_remote}/" ]]; then
            branch_names_to_yield+=("${ref#"refs/remotes/${default_remote}/"}")
        fi
    done
    local branch localbr remotebr
    for branch in "${branch_names_to_yield[@]}"; do
        # Take care to the behavior of "git rev-parse": this command may return
        # an invalid symbolic ref (with a non-null status code, which is
        # voluntarily discarded here) and create a bug with the test further
        # down. The option "--verify" is absolutely needed here.
        localbr="$(git rev-parse --verify --quiet "refs/heads/${branch}" || :)"
        remotebr="$(git rev-parse --verify --quiet "refs/remotes/${default_remote}/${branch}" || :)"
        # Do not attempt to recreate a branch that already exists and point to
        # the same revision (avoids useless noise in the output logs):
        if [[ -n "${localbr}" ]]; then
            if [[ "${localbr}" == "${remotebr}" ]]; then
                continue  # all is good, skip over this branch name
            else
                echo >&2 "[!] Branch \"${branch}\" already exist on \"${REPO_PATH}\" and its revision does not match its equivalent on the remote \"${default_remote}\"."
                return_status=1
                continue
            fi
        else
            # Recreate the branches locally from the remotes branch refs.
            # Please note that according to git-branch(1), doing so
            # automatically sets the appropriate remote tracking branch to the
            # settings of the newly created local branch:
            if ! git branch "${branch}" "refs/remotes/${default_remote}/${branch}"; then
                echo >&2 "[!] Failed creating local branch \"${branch}\" for \"${REPO_PATH}\" (\"git branch\" returned $?)."
                return_status=1
            fi
        fi
    done

    return "${return_status}"
}

main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
