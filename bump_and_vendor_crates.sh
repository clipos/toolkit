#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

# Get the basename of this program and the directory path to itself:
readonly PROGNAME="${BASH_SOURCE[0]##*/}"
readonly PROGPATH="$(realpath "${BASH_SOURCE[0]%/*}")"

# Full path to the repo root dir:
readonly TOOLKIT="${PROGPATH}"
readonly REPOROOT="$(realpath "${TOOLKIT}/..")"

# Update vendored Rust crates registry for just
rm -rf \
    "${REPOROOT}/assets/crates-io/index" \
    "${REPOROOT}/assets/crates-io/"*.crate \
    "${REPOROOT}/run/cargo"

mkdir -p "${REPOROOT}/run/cargo"

pushd "${REPOROOT}/run/cargo"
cargo new just
pushd "just"
echo "just = \"0.3.12\"" >> "Cargo.toml"
cargo update
popd
popd

# Install the cargo local-registry subcommand with:
# $ cargo install cargo-local-registry
cargo local-registry --sync \
    "${REPOROOT}/run/cargo/just/Cargo.lock" \
    "${REPOROOT}/assets/crates-io"

# vim: set ts=4 sts=4 sw=4 et ft=sh:
