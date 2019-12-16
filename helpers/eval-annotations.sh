#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

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

set -e -u -o pipefail

# Do not run as root
if [[ "${EUID}" == 0 ]]; then
    >&2 echo "[*] Do not run as root!"
    exit 1
fi

readonly SELFNAME="${BASH_SOURCE[0]##*/}"
readonly SELFPATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

if [[ -z "${REPO_PATH:-}" ]]; then
    cat >&2 <<EOF
ERROR: Missing repo environment variables (REPO_*).

This script is intended to be run via the "repo forall" command, such as:

  $ repo forall [<project>...] -c '${0##*/} [<arg>...]'

Make sure to either use absolute paths for the command to launch or to have
activated the CLIP OS toolkit environment (see the "activate" file) to expose
the CLIP OS toolkit helper scripts in your PATH. This requirement is explained
by the fact that "repo forall" changes the current working directory before
invoking the specified command (commands are invoked from within each repo
project directory).

See "repo help forall" for more details. The above example is not exhaustive.
EOF
    exit 1
fi

main() {
    local exit_code=0

    case "${1:-}" in
        declare-upstreams)
            echo "[*] Starting to declare upstreams for \"${REPO_PATH}\"..."
            if eval_annotations "UPSTREAM" declare_upstreams "URL" "REFSPECS"; then
                echo "[*] Upstreams declaration for \"${REPO_PATH}\" has ended successfully."
            else
                echo "[X] Upstreams declaration for \"${REPO_PATH}\" has ended with errors."
                exit_code=1
            fi
            ;;
        verify)
            echo "[*] Starting to verify references for \"${REPO_PATH}\"..."
            if eval_annotations "VERIFY" verify "KEYRINGS" "REFS" "REFS_EXCLUDE"; then
                echo "[*] References verification for \"${REPO_PATH}\" has ended successfully."
            else
                echo "[X] References verification for \"${REPO_PATH}\" has ended with errors."
                exit_code=1
            fi
            ;;
        *)
            echo >&2 "ERROR: Unknown command"
            echo >&2 "Available commands:"
            echo >&2 "- declare-upstreams"
            echo >&2 "- verify"
            exit_code=1
            ;;
    esac

    exit "${exit_code}"
}


#   eval_annotations <category> <callback> <items>...
#
# This function evaluates the repo project annotations prefixed by the category
# name (e.g., <category>_<index>_<item>) and call the given callback function
# with the appropriate argument list (i.e., the values held by each annotation
# items in the order that were given to eval_annotations).
#
# Each index triggers a call to the callback function provided that the items
# specified to eval_annotations (last arguments) could be found. Missing items
# are tolerated provided that they are part of the last arguments to the
# callback function (when this one is variadic).
# As a consequence, callback functions MUST check that their mandatory
# arguments are given.
eval_annotations() {
    local category="${1:?eval_annotations: missing category as 1st arg}"
    local call="${2:?eval_annotations: missing callback function as 2nd arg}"
    shift 2
    : "${@:?eval_annotations: missing item(s) as last argument(s)}"

    # Loop to be exited when the annotations <category>_X_ITEM (with X being
    # the integer sequence and ITEM being the items set provided as argument
    # list to this function) are exhausted:
    local args item latest_item_missed var
    local index=0
    local nb_callback_failures=0
    while true; do
        attempt_callback=1  # always attempt callback call
        latest_item_missed=0  # we begin with a new index, we missed nothing
        args=()  # hold the arg list to be passed to the callback function

        # lookup all the annotations corresponding to the expected items to
        # construct the callback function command line:
        for item in "$@"; do
            var="REPO__${category}_${index}_${item:?eval_annotations: item cannot be empty string}"

            if [[ -z "${!var+defined}" ]]; then
                # i.e. var is not defined (empty value is considered defined!)

                # OK, so we miss this item. This is tolerated but every
                # subsequent items for this category index MUST be missed as
                # well.
                # Otherwise an annotation is missing in the manifest. On
                # contrary we will consider that we have exhausted the
                # annotations for this category index.
                latest_item_missed=1
                continue

            elif [[ "${latest_item_missed}" -ne 0 ]]; then
                echo >&2 "  [!] \"${var#REPO__}\" annotation has been found but another annotation for this category index is required but missing."
                echo >&2 "  [!] Callback \"${call}\" for these category index annotations (${category}_${index}_*) won't be attempted."
                attempt_callback=0
                break
            fi

            args+=("${!var}")
        done

        if [[ "${#args[@]}" -eq 0 && "${attempt_callback}" -ne 0 ]]; then
            # No args (with the fact that the callback would have been
            # attempted) means that absolutely no annotations has been found
            # for this category index.
            # Therefore we can consider that we have exhausted all the
            # annotation indexes.

            if [[ "${nb_callback_failures}" -ne 0 ]]; then
                # Avoid integer overflow on return statuses (they are
                # byte-long, i.e. returning 256 is equivalent to returning 0):
                return 1
            else
                return 0
            fi
        fi

        if [[ "${attempt_callback}" -eq 0 ]] || \
                ! "${call}" "${index}" "${args[@]}"; then
            (( nb_callback_failures++ )) || :
        fi

        (( index++ )) || :
    done
}

#   declare_upstreams <annotation-index> <git-remote-URL> <refspecs>
#
# This function is a callback function to provide to the eval_annotations
# function. It declares the upstream Git remote "remote<INDEX>" tied to the
# specified URL and add to the fetch mapping references the given refspecs
# (which must be fully-qualified refspecs with +?<remote>:<local> references
# mapping).
# As a consequence, this enables the developer to update the dedicated local
# branches (meant to track the upstream projects for development convenience)
# automatically when doing a "git fetch <upstream-remote-name>".
# Multiple refspecs can be given for an upstream provided they are
# whitespace-separated.
# The syntax in the "refspecs" string follows what is accepted by the command
# "git fetch" (see chapter "Git Internals - The Refspec" of the Git Book for
# more details).
#
# As an example, the following configuration:
#
#   <project name="src_external_linux" path="src/external/linux">
#     <annotation name="UPSTREAM_0_URL" value="https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git" />
#     <annotation name="UPSTREAM_0_REFSPECS" value="refs/heads/linux-4.16.y:refs/heads/upstream/stable-4.16 refs/tags/v*:refs/tags/v*" />
#     <annotation name="UPSTREAM_1_URL" value="https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git" />
#     <annotation name="UPSTREAM_1_REFSPECS" value="refs/heads/master:refs/heads/upstream/master refs/tags/v*:refs/tags/v*" />
#   </project>
#
# will declare two Git remotes ("upstream0" and "upstream1") that automatically
# updates the local branches "upstream/stable-4.16" and "upstream/master" (as
# well as the tags also specified in each refspec) whenever the user does a
# "git fetch upstreamX" (with X being 0 and 1).
declare_upstreams() {
    local index="${1:?declare_upstreams: missing annotation index as 1st arg}"
    local url="${2:?declare_upstreams: missing remote URL as 2nd arg}"

    local refspecs
    # do not evaluate globs by transforming the list of refspecs to an array
    read -ra refspecs <<< "${3:?declare_upstreams: missing refspecs as 3rd arg}"

    local remote="upstream${index}"

    echo "  [+] Declaring remote \"${remote}\" pointing to \"${url}\""

    # This always overwrites pre-existing remotes!
    git remote remove "${remote}" 2>/dev/null || :
    git remote add -- "${remote}" "${url}"

    # Define all the refspecs into that remote:
    local refmap
    for refmap in "${refspecs[@]}"; do
        # safety assertion
        if ! [[ "${refmap}" =~ ^\+?refs/.+:refs/.+$ ]]; then
            echo "  [!] Bad refspec \"${refmap}\". You must use a fully-qualified refspec."
            echo "      Skipping this refspec."
            return 1
        elif [[ "${refmap}" =~ ^\+ ]]; then
            echo "  [-] Careful! The refspec \"${refmap}\" implies that Git would blindly force-update the local references if the upstream rewrote their history."
            echo "      This is just a warning message."
        fi
        # this should not fail:
        git config --add "remote.${remote}.fetch" "${refmap}"
    done
}


#   verify <annotation-index> <keyring-dirs> <ref-patterns> [<ref-patterns-to-exclude>]
#
# This function is a callback function to provide to the eval_annotations
# function. It verifies the OpenPGP signatures of the requested Git reference
# list (where standard globs can be used), excluding other Git references list
# (if provided and where standard globs can also be used to describe excluding
# patterns) against the specified keyring.
# The keyring is defined by a whitespace-separated list of directories that can
# be found in the pubkeys folder of the manifest repository (the one considered
# by repo under .repo/manifests, not the out-of-band manifest repository
# sitting at the root of the source tree for the developer convenience).
#
# As an example, the following configuration:
#
#   <project name="src_external_linux" path="src/external/linux">
#     <annotation name="VERIFY_0_KEYRINGS" value="clipos/anssi" />
#     <annotation name="VERIFY_0_REFS" value="refs/heads/* refs/tags/*-clipos" />
#     <annotation name="VERIFY_0_REFS_EXCLUDE" value="refs/heads/upstream/*" />
#     <annotation name="VERIFY_1_KEYRINGS" value="linux/maintainers" />
#     <annotation name="VERIFY_1_REFS" value="refs/heads/upstream/stable/*" />
#   </project>
#
# will verify all the local branches not contained in the branch namespace
# "upstream/" and tags ending with "-clipos" with the keyring holding the
# public keys of the CLIP OS project maintnainers at ANSSI for the project
# "src/external/linux".
verify() {
    local index="${1:?verify: missing annotation index as 1st arg}"
    local keyrings
    # use an array for homogeneity with the rest of the code
    read -ra keyrings <<< "${2:?verify: missing keyrings as 2nd arg}"
    local ref_patterns
    # do not evaluate globs by transforming the list of refspecs to an array
    read -ra ref_patterns <<< "${3:?verify: missing ref_patterns as 3rd arg}"
    local ref_patterns_to_exclude
    # do not evaluate globs by transforming the list of refspecs to an array
    read -ra ref_patterns_to_exclude <<< "${4:-}"  # this can be omitted/empty

    # Identify the repo root (required to find the keyrings dir location)
    local repo_root
    repo_root="${PWD%/${REPO_PATH%/}}" # strip also the trailing slash
    # safety check assertion:
    if [[ "${repo_root}" == "${PWD}" ]]; then
        echo >&2 "  [!] Could not compute repo root path from CWD. :("
        return 1
    fi

    # The canonicalized absolute path to the keyrings directory in the run
    # working directory for the CLIP OS toolkit. It is important that this
    # variable holds an absolute path!
    local keyrings_dir
    keyrings_dir="$(realpath "${repo_root}/run/keyrings/")"

    # Query Git to retrieve all the available refs into an array
    local all_refs_str all_refs
    all_refs_str="$(git show-ref | awk '{ printf $2" " }')"
    # use an array for homogeneity with the rest of the code
    read -ra all_refs <<< "${all_refs_str}"

    # Select the refs we want to consider but exclude the ones we do not want:
    local candidate_ref ref_pattern include_matches exclude_matches
    local refs=()  # holds all the refs we consider for verification
    for candidate_ref in "${all_refs[@]}"; do
        include_matches=0
        exclude_matches=0
        # Process the ref patterns to include...
        for ref_pattern in "${ref_patterns[@]}"; do
            # no quotes on RHS because we want Bash to process the globs
            # shellcheck disable=SC2053
            if [[ "${candidate_ref}" == ${ref_pattern} ]]; then
                include_matches=1
                break  # no need to process more patterns
            fi
        done
        # ...and then process the ref patterns to exclude (if provided).
        for ref_pattern in "${ref_patterns_to_exclude[@]}"; do
            # no quotes on RHS because we want Bash to process the globs
            # shellcheck disable=SC2053
            if [[ "${candidate_ref}" == ${ref_pattern} ]]; then
                exclude_matches=1
                break  # no need to process more patterns
            fi
        done
        if [[ "${include_matches}" -eq 1 && "${exclude_matches}" -eq 0 ]]; then
            refs+=("${candidate_ref}")
        fi
    done

    # Ensure all the keyrings specified are well present and built in the
    # keyrings directory (otherwise, this function should fail):
    local keyring keyring_path
    for keyring in "${keyrings[@]}"; do
        # As it is done by "create-keyrings.sh", all the keyrings directories
        # are flattened with percent chars replacing the slashes:
        keyring_path="${keyrings_dir}/${keyring//\//%}"

        # Probe for existence and accessibility of the selected keyring
        if ! [[ -d "${keyring_path}" && -r "${keyring_path}" ]]; then
            echo >&2 "  [!] Could not find any keyring \"${keyring}\"."
            echo >&2 "      Ensure to have run properly \"create-keyrings.sh\" with a properly synchronized CLIP OS source tree."
            return 1
        fi
    done

    # We can now (at last!) verify the refs:
    local keyring keyring_path ref ref_type verify_fail nb_verify_failures
    nb_verify_failures=0
    for ref in "${refs[@]}"; do
        verify_fail=1  # by default the ref is not verified

        # Get the type of the ref (either commit or tag):
        ref_type="$(git cat-file -t "${ref}" 2>/dev/null || :)"
        if [[ -z "${ref_type}" ]]; then
            # This should never happen as we already built the "refs" list from
            # the refs Git could see above. But nevermind...
            echo >&2 "  [!] Unexpected error: could not find any ref matching \"${ref}\"."
            echo >&2 "      Could not verify this ref. Skipping it and considering it as a verification failure."
            (( nb_verify_failures++ )) || :
            continue
        elif ! [[ "${ref_type}" =~ ^(commit|tag)$ ]]; then
            echo >&2 "  [!] The Git ref \"${ref}\" is neither a commit nor a tag."
            echo >&2 "      Could not verify this ref. Skipping it and considering it as a verification failure."
            (( nb_verify_failures++ )) || :
            continue
        fi

        for keyring in "${keyrings[@]}"; do
            # As it is done by "create-keyrings.sh", all the keyrings
            # directories are flattened with percent chars replacing the
            # slashes:
            keyring_path="${keyrings_dir}/${keyring//\//%}"

            if GNUPGHOME="${keyring_path}" git "verify-${ref_type}" "${ref}"; then
                verify_fail=0  # success in verification, yay \o/
                break  # no need to try with other keyrings
            fi
        done

        if [[ "${verify_fail}" -eq 0 ]]; then
            echo >&2 "  [*] Verification succeeded for ref \"${ref}\" in project \"${REPO_PROJECT}\""
        else
            echo >&2 "  [!] Verification FAILED for ref \"${ref}\" in project \"${REPO_PROJECT}\"."
            (( nb_verify_failures++ )) || :
        fi
    done

    if [[ "${nb_verify_failures}" -ne 0 ]]; then
        # Avoid integer overflow on return statuses (they are
        # byte-long, i.e. returning 256 is equivalent to returning 0):
        return 1
    else
        return 0
    fi
}


main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
