#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

# Little foolproof check to avoid messing up the interactive shell of the
# inattentive user who does a "source toolkit/setup.sh" after a failed call to
# "source toolkit/activate" that invited him/her to call (but NOT sourced!)
# this present script before proceeding.
if [[ "${BASH_SOURCE[0]:-}" != "${0:-}" ]]; then
    echo >&2 "Warning! This script is not meant to be sourced. Call it normally like any other executable shell script."
    return 1
fi

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Get the basename of this program and the directory path to itself
readonly PROGNAME="${BASH_SOURCE[0]##*/}"
readonly PROGPATH="$(realpath "${BASH_SOURCE[0]%/*}")"

# Check if not running as root
if [[ "$(id -u)" -eq 0 ]]; then
    echo >&2 "You should not be running this as root. Aborting."
    exit 1
fi

main() {
    echo "[+] Building cosmk..."
    pushd "${PROGPATH}/cosmk" > /dev/null
    go build -o cosmk -mod=vendor -ldflags "-X main.version=$(cat version | tr -d '\n')" ./src
    popd > /dev/null

    local -r reporoot="$(realpath ${PROGPATH}/../)"

    pushd "${reporoot}" > /dev/null
    mkdir -p run/bin
    mv "toolkit/cosmk/cosmk" "run/bin/cosmk"
    popd > /dev/null

    # Symlink the helper scripts available in the toolkit's "helpers" directory
    # in the "run/bin" directory in order to make them appear via PATH.
    # This eases the ability to call those scripts for the user (espcially for
    # the scripts intended to be used with "repo forall" as repo changes the
    # CWD).
    echo "[*] Installing helpers..."
    for item in "${PROGPATH}/helpers/"*; do
        if [[ -x "${item}" ]]; then
            # Assuming GNU coreutils for the "--relative-to" option of realpath
            ln -snf \
                "$(realpath --relative-to="${reporoot}/run/bin" "${item}")" \
                "${reporoot}/run/bin/${item##*/}"
        fi
    done
    unset item

    cat >&2 <<END_OF_BANNER
[+] Please choose one of the following option to make the cosmk tool available
    in your shell sessions:

    * Source the toolkit/activate script in your current session:

      $ source toolkit/activate

    Or:

    1. Move the 'cosmk' binary to a path already in your \$PATH:

       $ mv '${reporoot}/run/bin/cosmk' ${HOME}/.bin/cosmk # For example

    2. Enable Bash or Zsh completion by adding the following code in your
       '.bashrc' or '.zshrc':

       # Bash
       eval "\$(cd ${reporoot}; cosmk --completion-script-bash)"

       # Zsh
       eval "\$(cd ${reporoot}; cosmk --completion-script-zsh)"
END_OF_BANNER
}

main

# vim: set ts=4 sts=4 sw=4 et ft=sh tw=79:
