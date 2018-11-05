#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# This script checks that the Git LFS backed repositories (those repositories
# must be part of the repo group "lfs", see the manifest file) have all the Git
# LFS objects properly downloaded and checked out in the working tree.

set -e -u -o pipefail

readonly SELFNAME="${BASH_SOURCE[0]##*/}"
readonly SELFPATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

# The absolute path to the repo source tree root (this line depends on the
# location of the script within the repo source tree):
readonly REPOROOT="$(realpath "${SELFPATH}/../..")"

main() {
    local mode='verbose'
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            -q|--quick)
                mode='quick'
                shift ;;
            -v|--verbose)
                mode='verbose'
                shift ;;
            --) shift; break ;;
            *)  echo >&2 "ERROR: Unknown option $1"; return 1 ;;
        esac
    done

    case "${mode}" in
        quick)
            quick_but_silent_check
            ;;
        verbose)
            verbose_but_slow_check
            ;;
        *)
            echo >&2 "ERROR: Unexpected error"
            return 1;;
    esac
}

quick_but_silent_check() {
    # shellcheck disable=SC2016
    repo forall -g lfs -c 'git lfs ls-files | awk '"'"'($2 != "*") {exit(1)}'"'"
}

verbose_but_slow_check() {
    local return_code=0

    # Get the list of the repo project names that are part of the "lfs" group:
    local lfs_projects
    # shellcheck disable=SC2016
    read -ra lfs_projects <<< "$(repo forall -g lfs -c 'echo "${REPO_PROJECT}"' | xargs)"
    echo " [*] ${#lfs_projects[@]} projects in the \"lfs\" repo group:"
    echo "       ${lfs_projects[*]}"

    local lfs_project
    for lfs_project in "${lfs_projects[@]}"; do
        # "git lfs ls-files" reports the status of all the Git LFS tracked objects
        # in the tree. An asterisk (*) means that the object has been properly
        # downloaded in the Git LFS store and checked out in the current working
        # tree:
        # shellcheck disable=SC2016
        if ! repo forall "${lfs_project}" -c 'git lfs ls-files |
                awk '"'"'($2 != "*") {exit(1)}'"'"; then
            return_code=1
            echo >&2 "   [-] Missing LFS objects in repo project \"${lfs_project}\"."
        fi
    done

    if [[ "${return_code}" -ne 0 ]]; then
        echo >&2 " [!] Some Git LFS backed repositories are missing Git LFS objects."
        echo >&2 "     Ensure Git LFS filters are enabled in your environment and fetch the missing"
        echo >&2 "     files with the command \"git lfs pull\"."
    fi

    return "${return_code}"
}

main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
