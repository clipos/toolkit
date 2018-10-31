#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# This script creates the GnuPG 2 keyrings in the CLIP OS toolkit runtime
# directory (<repo-root>/run/keyrings) from the keyrings found in the manifest
# managed by repo (<repo-root>/.repo/manifests/keyrings).

set -e -u -o pipefail

readonly SELFNAME="${BASH_SOURCE[0]##*/}"
readonly SELFPATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

# The absolute path to the repo source tree root (this line depends on the
# location of the script within the repo source tree):
readonly REPOROOT="$(realpath "${SELFPATH}/../..")"

# The absolute path (from the root of the repo source tree) to the project
# holding all the OpenPGP public keys that will compose the keyrings to create:
readonly KEYRINGS="${REPOROOT}/.repo/manifests/keyrings"

main() {
    local exit_code=0

    # safety assertion
    if ! [[ -d "${REPOROOT}/.repo" ]]; then
        echo >&2 "ERROR: REPOROOT variables does not seem to be a repo root."
        exit 1
    fi

    # This array holds the keyring names (i.e. the subpaths within the
    # keyrings directory in the manifest repository on which repo is working on
    # and that hold OpenPGP ASCII-armored public keys):
    local keyring_names=()

    # Find all the keyring names:
    local keyrings_canonical_abspath line keyring_name
    keyrings_canonical_abspath="$(realpath "${KEYRINGS}")"
    while IFS='' read -r -d $'\0' line; do
        # strip the keyrings_canonical_abspath and the file name from the
        # line returned by find to get the keyring name:
        keyring_name="${line#${keyrings_canonical_abspath}/}"
        keyring_name="${keyring_name%/*.asc}"

        # safety assertion on the keyring names
        if ! [[ "${keyring_name}" =~ ^[a-zA-Z0-9_\.-]+(/[a-zA-Z0-9_\.-]+)*$ ]]; then
            echo >&2 "ERROR: Invalid keyring name found: ${keyring_name}"
            exit 1
        fi

        if ! contains "${keyring_name}" "${keyring_names[@]}"; then
            keyring_names+=("${keyring_name}")
        fi
    done < <(find "${keyrings_canonical_abspath}" -type f -name '*.asc' -print0)

    # Creates the GnuPG 2 keyrings directory in the "run" directory (i.e. the
    # working directory environment for all the CLIP OS toolkit resources):
    mkdir -p "${REPOROOT}/run"
    local keyrings_base_path="${REPOROOT}/run/keyrings"

    # It's easier to recreate the GPG keyrings from scratch at each run of this
    # script rather than trying to update the potentially existing ones (which
    # would imply to delete pubkeys that may have disappeared from the keyrings
    # repository). Since this keyrings working directory only serves for
    # verifying repositories and nothing else (at current state of writing), we
    # can safely obliterate its content and recreate everything.
    rm -rf "${keyrings_base_path:?}"
    mkdir "${keyrings_base_path}"

    # As we do not want to pollute the GnuPG home directories with arbitrary
    # sub-directories, the keyrings entities tree is flattened into a list of
    # directories (where the slash chars from the keyring names are replaced
    # with percent chars):
    local keyring_name keyring_path
    for keyring_name in "${keyring_names[@]}"; do
        keyring_path="${keyrings_base_path}/${keyring_name//\//%}"
        mkdir "${keyring_path}"
        chmod 0700 "${keyring_path}"

        create_gpg_keyring "${keyring_path}" "${KEYRINGS}/${keyring_name}/"*.asc
    done

    exit "${exit_code}"
}


#   contains <candidate> [<element>...]
#
# Handy utility function that process a list of <element>s and returns 0
# (success) if the <candidate> element could be found in the list.
# Otherwise it returns 1 (failure).
contains() {
    local candidate="${1?contains() requires a candidate element to seek}"
    shift
    local element
    for element in "$@"; do
        if [[ "$element" == "$candidate" ]]; then
            return 0
        fi
    done
    return 1
}

#   create_gpg_keyring <gnupghome> <pubkeys-to-import>...
#
# Creates a GnuPG keyring in the <gnupghome> directory with all the keyrings
# specified as last arguments imported. To avoid any unnecessary warning, all
# the public keys imported are marked as "ultimately" trusted within the
# created GnuPG keyring.
create_gpg_keyring() {
    local keyring_path="${1:?create_gpg_keyring: missing arg}"
    shift
    local pubkeys=("${@:?create_gpg_keyring: missing pubkeys}")

    # GnuPG 2 command line utility is tricky to use in unattended scripts. Here
    # is a set of common options for gpg to prevent some unrequired features of
    # GnuPG in our specific case.
    cat > "${keyring_path}/gpg.conf" <<EOF
# Usage of gpg is unattended:
batch

# Make sure that the TTY (terminal) is never used for any output.
# This option is needed in some cases because GnuPG sometimes prints
# warnings to the TTY even if --batch is used.
no-tty

# Since it is quite hard to **really** disable the use of any PGP trust model
# (even with "--trust-model=always", gpg keeps yelling some warning messages
# stating that a given key is untrusted, even though we told it not to consider
# any trust model), we deliberately use the PGP trust model but we circumvent
# it by setting the trust level to "ultimate" to all the imported public keys
# in those temporary keyrings.
# The PGP trust model is useless in our case since we assume that all the keys
# from the keyrings directory (of the manifest repository currently processed
# by repo) are trusted. However, this is true ONLY IF the authenticity of that
# manifest repository has been checked before! Checking the authenticity of the
# manifest repository is still the duty of the user.
trust-model pgp

# There is no need to show the UID validity (i.e. trust level for the keys) as
# we consider a dummy PGP trust model here.
list-options no-show-uid-validity
verify-options no-show-uid-validity

# Do not try to fetch any key from keyservers or with any protocol
no-auto-key-locate
no-auto-key-retrieve

# Dirmngr is absolutely useless in our case:
disable-dirmngr

# When showing a PGP KeyID, always use the long form (even if using full-length
# fingerprints should always be preferred):
keyid-format 0xlong

# Assume that command line arguments are given as UTF-8 strings:
utf8-strings
EOF

    # There is a length restriction on the GNUPGHOME path (see
    # https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=847206). This length of
    # maximum 108 chars may be easily exceeded when this script is called in a
    # CI job context. Therefore we need to rely on another temporary location
    # for the gpg-agent socket (and not the GNUPGHOME):
    printf '%%Assuan%%\nsocket=/dev/shm/S.gpg-agent.tmp\n' > "${keyring_path}/S.gpg-agent"
    printf '%%Assuan%%\nsocket=/dev/shm/S.gpg-agent.ssh.tmp\n' > "${keyring_path}/S.gpg-agent.ssh"
    printf '%%Assuan%%\nsocket=/dev/shm/S.gpg-agent.extra.tmp\n' > "${keyring_path}/S.gpg-agent.extra"
    printf '%%Assuan%%\nsocket=/dev/shm/S.gpg-agent.browser.tmp\n' > "${keyring_path}/S.gpg-agent.browser"

    local status=0
    # Bash-fu warning: The following construct is a hack to get around a
    # long-known bug with the errexit option (aka. set -e) in Bash subshells:
    # the errexit option is tied to the parent shell. As a consequence a
    # command run in a subshell and returning a non-null value that would cause
    # that subshell to stop will actually (and wrongfully) cause the parent
    # shell to stop (even if the parent shell catches the eventual error status
    # of that subshell).
    # To put it differently, this construct (disabling errexit in the parent
    # shell to enable it only in the subshell) permits to circumvent this bug.
    # As a matter of fact, this enables us to have a kind of try/catch block in
    # pure Bash.
    set +e; (
        set -e;

        # Export the GNUPG home for the following gpg commands in that subshell
        # (this variable exportation is limited to the current subshell):
        export GNUPGHOME="${keyring_path}"

        # Attempt creation and connection to the gpg-agent with the parameters
        # set above in the $GNUPGHOME/S.gpg-agent files:
        gpg-connect-agent <<< 'GETINFO socket_name'

        gpg --fast-import -- "${pubkeys[@]}"

        # Ultimately (6 = ultimate) trust all the keys imported in the keyring:
        gpg --list-keys --with-colons |
            awk -F':' '($1 == "pub") { pubkey=1; next; }
            ($1 == "fpr" && pubkey ) { print $10":6:"; pubkey=0; }' |
                gpg --import-ownertrust

        # Rebuilding the trustdb is required after having updated it:
        gpg --check-trustdb

    ); status="$?"; set -e;  # Re-enable errexit for parent shell (see above)

    # Gracefully terminates the gpg-agent associated to the GNUPGHOME used
    # by the previous command (this prevents from polluting the process
    # namespace of the user with dangling gpg-agents):
    GNUPGHOME="${keyring_path}" gpgconf --kill gpg-agent || :

    return "${status}"
}

main "$@"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
