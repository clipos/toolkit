#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

set -e -u -o pipefail

# Each project in the manifest can have a set of annotations, as shown in the
# dummy example below:
#
#   <project name="src_external_linux" path="src/external/linux" >
#     <annotation name="CATEGORY_0_ITEM_A" value="item a for the first category" />
#     <annotation name="CATEGORY_0_ITEM_B" value="item b for the first category" />
#     <annotation name="CATEGORY_1_ITEM_A" value="item a for the second one" />
#     <annotation name="CATEGORY_1_ITEM_B" value="item b for the second one" />
#   </project>
#
# Annotation names must follow this nomenclature
# "<CATEGORY>_<INDEX>_<ITEM-NAME>" with INDEX being a positive integer (indexes
# start at 0) without leading zeroes.

main() {
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

    case "${1:-}" in
        pull-upstream)
            echo "[*] Starting to fetch upstream for ${REPO_PATH}"
            eval_annotations "UPSTREAM" pull_upstream "URL" "REFSPECS"
            ;;
        *)
            echo >&2 "ERROR: Unknown command"
            echo >&2 "Available commands:"
            echo >&2 "- pull-upstream"
            exit 1
            ;;
    esac
}


#   eval_annotations <category> <callback> <items>...
#
# This function evaluates the repo project annotations prefixed by the category
# name (e.g., <category>_<index>_<item>) and call the given callback function
# with the appropriate argument list (i.e., the values held by each annotation
# items in the order that were given to eval_annotations).
# Each index triggers a call to the callback function provided that all the
# items specified to eval_annotations could be found (otherwise this function
# stops processing further annotations without warning). Indexes are
# incremented until no annotations could be found.
eval_annotations() {
    local category="${1:?eval_annotations: missing category as 1st arg}"
    local call="${2:?eval_annotations: missing callback function as 2nd arg}"
    shift 2
    : "${@:?eval_annotations: missing item(s) as last argument(s)}"

    # Loop to be exited when the annotations <category>_X_ITEM (with X being
    # the integer sequence and ITEM being the items set provided as argument
    # list to this function) are exhausted:
    local args item var index=0
    while true; do
        args=()  # hold the arg list to be passed to the callback function
        for item in "$@"; do
            var="REPO__${category}_${index}_${item:?eval_annotations: items cannot be empty string}"
            if [[ -z "${!var:-}" ]]; then
                # annotations exhausted, exit the loop
                return 0
            fi
            args+=("${!var}")
        done
        "${call}" "${index}" "${args[@]}"
        let index++ || :
    done
}


#   pull_upstream <annotation-index> <git-remote-URL> <refspecs>
#
# This function is a callback function to provide to the eval_annotations
# function. It fetches the upstream Git references specified in the refspecs
# string (multiple refspec can be given provided they are whitespace-separated)
# from the Git remote URL and create the expected local branches according to
# the refspecs.
#
# As an example:
#
#   <project name="src_external_linux" path="src/external/linux">
#     <annotation name="UPSTREAM_0_URL" value="https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git" />
#     <annotation name="UPSTREAM_0_REFSPECS" value="refs/heads/linux-4.16.y:refs/heads/upstream/stable-4.16 refs/tags/v*:refs/tags/v*" />
#     <annotation name="UPSTREAM_1_URL" value="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git" />
#     <annotation name="UPSTREAM_1_REFSPECS" value="refs/heads/master:refs/heads/upstream/master refs/tags/v*:refs/tags/v*" />
#   </project>
#
# This configuration creates two new remotes (upstream0 and upstream1), fetch
# their references and create the local branches according to the given
# refspecs. The syntax in the refspecs string follows what is accepted by the
# command "git fetch" (see chapter "Git Internals - The Refspec" of the Git
# Book for more details).
pull_upstream() {
    local index="${1:?pull_upstream: missing annotation index as 1st arg}"
    local url="${2:?pull_upstream: missing remote URL as 2nd arg}"

    local refspecs
    # do not evaluate globs by transforming the list of refspecs to an array
    read -a refspecs <<< "${3:?pull_upstream: missing refspecs as 3rd arg}"

    local remote="upstream${index}"

    echo "[+] Fetching refspecs ${refspecs[*]}"

    local current
    current="$(git remote get-url "${remote}" 2> /dev/null || :)"
    if [[ "${current}" != "${url}" ]]; then
        git remote remove "${remote}" 2> /dev/null || :
        git remote add -- "${remote}" "${url}"
    fi
    git fetch --no-tags -- "${remote}" "${refspecs[@]}"

    echo  # line break to visually split the result of each upstream fetch
}


main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
