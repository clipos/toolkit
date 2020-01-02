#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2019 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Do not run as root
if [[ "${EUID}" == 0 ]]; then
    >&2 echo "[*] Do not run as root!"
    exit 1
fi

main() {
    if [[ -z "$(command -v cosmk)" ]]; then
        >&2 echo "[!] Could not find \"cosmk\". Aborting."
        exit 1
    fi
    local -r repo_root="$(cosmk repo-root-path)"
    local -r product="$(cosmk product-name)"
    local -r version="$(cosmk product-version)"

    # Full path to the vendor dirs:
    local -r vendor="${repo_root}/assets/gentoo"

    local -r base_url='http://distfiles.gentoo.org/releases/amd64/autobuilds'

    local -r kind='stage3-amd64-hardened+nomultilib'
    local -r image='localhost/gentoo/hardened'

    local -r latest_url="${base_url}/latest-${kind}.txt"

    echo "[*] Looking for latest version for ${kind}..."
    local -r url="$(curl -sSf "${latest_url}" | grep -v "^#" | cut -d\  -f 1)"
    local -r version="$(echo ${url} | cut -d/ -f 1)"

    pushd "${vendor}" > /dev/null

    # Is this stage3 already available?
    local -r dest="${kind}-${version}.tar.xz"
    if [[ -f "${dest}" ]]; then
        echo "[*] ${kind} image for version ${version} already available"
        echo "[*] Done"
        exit 0
    fi

    echo "[*] Downloading ${kind} ${version}..."
    curl "${base_url}/${url}" --output "${dest}"
    curl "${base_url}/${url}.DIGESTS.asc" --output "${dest}.DIGESTS.asc"

    echo "[*] Verifying ${kind} ${version}..."
    gpg --verify "${dest}.tar.xz.DIGESTS.asc" "${dest}"
    # Ignore WHIRLPOOL hashes & check only the file that matter
    sed '/WHIRLPOOL/,+1 d' "${dest}.DIGESTS.asc" \
        | grep "${dest}" \
        | sha512sum -c --ignore-missing

    popd > /dev/null
}

main "${@}"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
