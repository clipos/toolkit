# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# Default recipes: iterative build reusing cached packages
all: clipos

# Build clipos then create QEMU image & run resulting image
all-run: clipos qemu

# Clean output folder and build everything in order. Use cached packages
clipos:
    just products/clipos/all

# Shortcut for development builds that do not change any packages
cbq:
    just products/clipos/core/configure
    just products/clipos/core/bundle
    just products/clipos/efiboot/configure
    just products/clipos/efiboot/bundle
    just products/clipos/qemu

# Build and run the QEMU image for testing
qemu:
    just products/clipos/qemu

# Run the QEMU image for testing
run:
    just products/clipos/qemu/run

# Clean all temporary output folders
clean:
    rm -rf ./out

# Clean all cache folders (packages). Everything will be rebuilt from scratch
clean-cache:
    rm -rf ./cache

# Clean the Python virtual env and all runtime temporary files
clean-run:
    rm -rf ./run

# Clean everything: out, cache & run folders
clean-all: clean clean-cache clean-run

# Build the documentation
doc:
  ./toolkit/helpers/build_doc.sh

# Open the documentation in the default browser
open-doc:
  xdg-open ./out/doc/_build/index.html

# Retrieve binary packages & SDK from the CI
get-cache:
    #!/usr/bin/env bash
    echo "This will be updated once the build infrastructure is in place."
    exit 0

# Helper command for 'repo forall -c <cmd>' output
rfa +cmd:
    repo forall -j 1 -c "echo \$REPO_PROJECT; {{cmd}}; echo ''"

# Helper command for pretty and selective 'repo forall -c <cmd>' output
# Warning: 'cmd' can not include arguments with spaces
rfm +cmd:
    repo forall -j 1 -c "${PWD}/toolkit/helpers/filter-most.sh {{cmd}}"

# Update Git remotes with the upstream defined in the manifest
declare-upstreams +projects='':
    repo forall {{projects}} -c "${PWD}/toolkit/helpers/declare-upstreams.sh"

# Fetch the Git references from upstream remotes defined with
# "declare-upstreams"
fetch-upstreams +projects='':
    repo forall {{projects}} -c "${PWD}/toolkit/helpers/fetch-upstreams.sh"

# repo status helper
status:
    repo status -j 1

# Switch to master branch for all projects
master:
    repo start master --all

# vim: set ts=4 sts=4 sw=4 et ft=sh:
