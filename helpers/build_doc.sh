#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

# Safety settings: do not remove!
set -o errexit -o nounset -o pipefail

main() {
    readonly repo_root_path="$(cosmk repo-root-path)"

    if [[ -z "${repo_root_path}" ]]; then
        echo "[!] CLIP OS toolkit environment not activated!"
        return 1
    fi

    # Cleanup
    rm -rf "${repo_root_path}/out/doc"
    mkdir -p "${repo_root_path}/out"

    # Setup the docroot with the Sphinx configuration
    cp -a "${repo_root_path}/toolkit/docroot" "${repo_root_path}/out/doc"

    # Add the tookit documentation
    cp -a "${repo_root_path}/toolkit/doc" "${repo_root_path}/out/doc/toolkit"

    # Add the CLIP OS product documentation
    # TODO: Make this generic accross products
    cp -a "${repo_root_path}/products/clipos/doc" "${repo_root_path}/out/doc/clipos"

    # Fix the index
    cat \
        "${repo_root_path}/out/doc/clipos/index.rst" \
        "${repo_root_path}/out/doc/toolkit/index.rst" \
        >> "${repo_root_path}/out/doc/index.rst"
    rm \
        "${repo_root_path}/out/doc/toolkit/index.rst" \
        "${repo_root_path}/out/doc/clipos/index.rst"

    # Build the HTML documentation
    cd "${repo_root_path}/out/doc"
    export SPHINXPROJ="CLIPOS"
    sphinx-build -b html -j auto . _build

    # Disable Jekyll processing for GitHub Pages hosting
    touch _build/.nojekyll

    # Set CNAME for GitHub Pages hosting
    echo "docs.clip-os.org" > _build/CNAME

    # Set minimal README
    cat > _build/README.md <<EOF
# Static content for docs.clip-os.org

See <https://docs.clip-os.org>.
EOF

    # Cleanup
    rm _build/.buildinfo
}

main $@

# vim: set ts=4 sts=4 sw=4 et ft=sh:
