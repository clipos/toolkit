#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Get the basename of this program and the directory path to itself:
readonly PROGNAME="${BASH_SOURCE[0]##*/}"
readonly PROGPATH="$(realpath "${BASH_SOURCE[0]%/*}")"

# Full path to the repo root dir:
readonly TOOLKIT="$(realpath "${PROGPATH}/..")"
readonly REPOROOT="$(realpath "${TOOLKIT}/..")"

# Update vendored Rust crates registry for just
rm -rf \
    "${REPOROOT}/assets/crates-io/index" \
    "${REPOROOT}/assets/crates-io/"*.crate \
    "${REPOROOT}/run/cargo"

mkdir -p "${REPOROOT}/run/cargo"

pushd "${REPOROOT}/run/cargo"

# Create a fake just project with all dependencies to retrieve crates
cargo new just
pushd "just"
cat >> "Cargo.toml" <<EOF
just            = "0.3.12"
ansi_term       = "0.11"
assert_matches  = "1.1.0"
atty            = "0.2.1"
brev            = "0.1.6"
clap            = "2.0.0"
dotenv          = "0.13.0"
edit-distance   = "2.0.0"
itertools       = "0.7"
lazy_static     = "1.0.0"
libc            = "0.2.21"
regex           = "1.0.0"
target          = "1.0.0"
tempdir         = "0.3.5"
unicode-width   = "0.1.3"
executable-path = "1.0.0"
EOF
cargo update
popd
popd

# Install the cargo local-registry subcommand with:
# $ cargo install cargo-local-registry
cargo local-registry --sync \
    "${REPOROOT}/run/cargo/just/Cargo.lock" \
    "${REPOROOT}/assets/crates-io"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
