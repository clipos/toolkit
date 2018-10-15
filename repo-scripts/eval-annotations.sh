#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

set -e -u -o pipefail

eval_annotations() {
    local call
    local index
    local template
    local var
    local args

    call="$1"
    shift
    index=0
    while true; do
        args=()
        for template in "$@"; do
            var="REPO__${template}_${index}"
            if [[ -z "${!var:-}" ]]; then
                return 0
            fi
            args+=("${!var}")
        done
        "${call}" "${index}" "${args[@]}"
        let index++ || :
    done
}

# Each project in the manifest can have a set of annotations, for example to
# fetch upstream updates:
#
#   <project name="src_external_linux" path="src/external/linux" >
#     <annotation name="UPSTREAM_0_URL" value="https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git" />
#     <annotation name="UPSTREAM_0_REFSPECS" value="refs/heads/linux-4.16.y:refs/heads/upstream/stable-4.16 refs/tags/v*:refs/tags/v*" />
#     <annotation name="UPSTREAM_1_URL" value="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git" />
#     <annotation name="UPSTREAM_1_REFSPECS" value="refs/heads/master:refs/heads/upstream/master refs/tags/v*:refs/tags/v*" />
#   </project>
#
# This configuration creates two new remotes (upstream0 and upstream1), fetch
# their references according to the given refspec(s) (i.e., fetch the specified
# refspecs and rename them locally according to the mapping the refspec
# describe, see chapter "Git Internals - The Refspec" of the Git Book for more
# details).

pull_upstream() {
    local index="$1"
    local git="$2"
    local refs
    # do not evaluate globs by transforming the list of refs to an array
    read -a refs <<< "$3"
    local remote="upstream${index}"
    local current

    echo "[+] Fetching references ${refs[*]}"

    current="$(git remote get-url "${remote}" 2> /dev/null || :)"
    if [[ "${current}" != "${git}" ]]; then
        git remote remove "${remote}" 2> /dev/null || :
        git remote add -- "${remote}" "${git}"
    fi
    git fetch --no-tags -- "${remote}" "${refs[@]}"

    # TODO: ask for git push..?
    echo
}

if [[ -z "${REPO_PATH:-}" ]]; then
    echo "ERROR: Missing environment variables" >&2
    echo "This script must be run with: repo forall [projects...] -c $0 <command>" >&2
    exit 1
fi

case "${1:-}" in
    pull-upstream)
        echo "[*] Starting to fetch upstream for ${REPO_PATH:-}"
        eval_annotations pull_upstream "UPSTREAM_GIT" "UPSTREAM_REFS"
        ;;
    *)
        echo "ERROR: Unknown command" >&2
        echo "Available commands:" >&2
        echo "- pull-upstream" >&2
        exit 1
        ;;
esac

# vim: set ts=4 sts=4 sw=4 et ft=sh:
