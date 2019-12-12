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

# Get build artifacts from CLIP OS CI

readonly SELFNAME="${BASH_SOURCE[0]##*/}"
readonly SELFPATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

# The absolute path to the repo source tree root (this line depends on the
# location of the script within the repo source tree):
readonly REPOROOT="$(realpath "${SELFPATH}/../..")"

main() {
    if [[ "${#}" -ne 1 ]]; then
        >&2 echo "[!] You must specify the URL from which artifacts will be fetched!"
        return 1
    fi

    local -r url="${1}"
    echo "[*] Retrieving artifacts from: ${url}"

    if [[ -z "${CLIPOS_KEEP_ARTIFACTS+x}" ]]; then
        >&2 echo "[!] Downloaded artifacts archives will be removed once extracted."
        >&2 echo "    To keep them, set the CLIPOS_KEEP_ARTIFACTS environment variable."
    fi

    # Make sure that we are at the repo root
    cd "${REPOROOT}"

    # List of artifacts to retrieve (SDKs, Core & EFIboot packages)
    artifacts=(
        'sdk.tar.zst'
        'core_pkgs.tar.zst'
        'efiboot_pkgs.tar.zst'
    )

    # Retrieve artifacts
    for a in "${artifacts[@]}"; do
        echo "[*] Downloading ${a}..."
        curl --proto '=https' --tlsv1.2 -sSf -o "${a}" "${url}/${a}"
    done

    # Retrieve the SHA256SUMS file and check artifacts integrity
    curl --proto '=https' --tlsv1.2 -sSf -o 'SHA256SUMS.full' "${url}/SHA256SUMS"

    # Only keep relevant checksums to avoid issues
    > 'SHA256SUMS'
    for a in "${artifacts[@]}"; do
        grep "${a}" 'SHA256SUMS.full' >> 'SHA256SUMS'
    done
    rm 'SHA256SUMS.full'

    echo "[*] Verifying artifacts integrity..."
    sha256sum -c 'SHA256SUMS'

    # Extract artifacts
    for a in "${artifacts[@]}"; do
        echo "[*] Extracting ${a}..."
        tar --extract --file "${a}" --warning=no-unknown-keyword
    done

    if [[ -z "${CLIPOS_KEEP_ARTIFACTS+x}" ]]; then
        for a in "${artifacts[@]}"; do
            echo "[*] Removing ${a}..."
            rm ${a}
        done
        echo "[*] Removing SHA256SUMS..."
        rm SHA256SUMS
    else
        echo "[*] You may now remove all downloaded artifacts with:"
        echo "    $ rm ${artifacts[@]} SHA256SUMS"
    fi

    echo "[*] Success!"
}

main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
