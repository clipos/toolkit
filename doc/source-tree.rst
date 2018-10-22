.. Copyright © 2018 ANSSI.
   CLIP OS is a trademark of the French Republic.
   Content licensed under the Open License version 2.0 as published by Etalab
   (French task force for Open Data).

Source tree organization
========================

This page is intended to give you a quick look of the overall organization of
the CLIP OS source tree as managed by the `repo
<https://source.android.com/setup/using-repo>`_ tool.

.. sidebar:: Non-exhaustive representation of the source tree

   This document has a structure that reflects the CLIP OS source tree but is
   not intended to be exhaustive. Some directories and files are intentionally
   missing as they do not matter to understand the organizational logic of the
   CLIP OS source tree.

.. contents:: Source tree contents
   :local:

.. admonition:: About the nomenclature of the underlying Git repositories
   :class: note

   The Git repositories behind each sub-directory of the CLIP OS source tree
   have a specific nomenclature intended to reflect the location of the Git
   repository "check-out" in the CLIP OS source tree.

   However, due to a limitation of GitHub-hosted repositories, we could not use
   forward slashes (``/``) in the Git repository names. Folder separators are
   therefore representated by underscores (``_``) in those repository names. If
   a sub-directory path already contains an underscore character, (e.g., for a
   third-party project under ``src/external/``), then the underlying Git
   repository name should have the problematic underscores stripped.

   .. csv-table:: Example of Git nomenclature
      :header: "Sub-directory path", "Underlying Git repository name"

      "``manifest/``", "``manifest``"
      "``products/clipos/``", "``products_clipos``"
      "``src/external/super_tool-linux/`` *(hypothetical)*", "``src_external_supertool-linux``"

``.repo/``
----------

The ``.repo`` directory holds the internal objects and files of the *repo*
tool.

.. admonition:: Do not mess with the contents of this directory
   :class: warning

   This ``.repo`` directory should not be messed with as it holds all the
   ``.git`` directories (i.e., the internal Git working directories) of all the
   sub-projects of this source tree managed by *repo*.

``assets/``
-----------

The sub-directories of this folder enclose all kinds of binaries or archive
files that are required either to build CLIP OS or to make the CLIP OS toolkit
work on a development environment that meets the :ref:`minimal environment
requirements <setup>`.

Providing those assets in the source tree also allows the usage of the CLIP OS
toolkit on an offline development setup (e.g., a build environment in a
security constrained infrastructure) and thus the lack of dependency on any
remote resource.

.. admonition:: Git LFS-backed repositories
   :class: warning

   As most of the underlying directories store large (and often binary) files,
   most of them rely on Git LFS for the revision of those large files to avoid
   cluttering their Git repository internal objects.

``assets/crates-io/``
~~~~~~~~~~~~~~~~~~~~~

This directory holds Rust crates from `crates.io <https://crates.io/>`_ that
serve to bootstrap and compile ``just`` (handy CLI tool to launch and abstract
sequences of shell commands).

``assets/debian/``
~~~~~~~~~~~~~~~~~~

This directory holds all the Debian packages used by the alternative SDK based
on a Debian environment.

``assets/distfiles/``
~~~~~~~~~~~~~~~~~~~~~

This directory holds the *distfiles* from Gentoo which serve for the Gentoo
**ebuild** files.

``assets/gentoo/``
~~~~~~~~~~~~~~~~~~

This directory contains the Gentoo *stage3* image that serves to bootstrap the
CLIP OS SDK.

``assets/toolkit/``
~~~~~~~~~~~~~~~~~~~

This directory holds all the Python packages that are dependencies of the CLIP
OS toolkit and need to be installed in the CLIP OS toolkit *virtualenv*.

These Python packages are originating from `PyPI <https://pypi.org/>`_ and must
only be source packages (in opposition with `wheel packages
<https://www.python.org/dev/peps/pep-0427/>`_) for legal and platform
compatibility reasons.

``cache/``
----------

This directory encloses all the build by-products that are not required to
build CLIP OS from scratch. This directory and its contents can be safely
erased from a building machine. In this case, the toolkit will then build
entirely from scratch.

The subdirectories in this folder will reflect the
``out/<product>/<version>/<recipe>/`` tree.

``cache/<product>/<version>/<recipe>/binpkgs/``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The binary packages produced by Portage/emerge during each *build* step and
that serve to build the target root images populated only with
runtime-dependencies (since the only way to deploy Portage packages without any
build-dependency is to emerge them only from binary packages, otherwise emerge
may need to emerge build-dependencies that may not be required or wanted in the
target root).

Another purpose of this directory is to provide emerge with a complete set of
the packages already compiled to speed up builds and image construction by
avoiding pointless identical package rebuilds (``emerge`` is configured to
properly manage the comparison between the compilation settings, the USE flag
sets of the binary packages and the packages to be deployed in a specified
target root and will trigger a rebuild if those do not match). Usually, on
developers workstations, the contents of this directory are meant to be
populated with the binary packages archive set produced by the continuous
integration server during the nightly build. This will prevent annoying and
time-consuming package builds on the developers' machines.

``manifest/``
-------------

This directory encloses all the repo manifest files in charge of constructing
the whole CLIP OS source tree.

.. admonition:: This is not the manifest check-out directory on which *repo* is
                working on.
   :class: warning

   *repo* does not work with the manifest files present in that specific
   directory but in the manifest files checked out in its internal directory
   (``.repo/manifests/``). Do not expect *repo* to take into account the
   changes you can introduce in that directory.

   The rationale behind this repository check-out is to serve only as a working
   directory for the developer to bring changes (before committing them) in the
   manifests files since it seems to be a bad practise to modify directly the
   manifests on which ``repo`` operates in ``.repo/manifests/``. This
   ``manifest/`` directory serves also as a working directory for the
   ``cosmk snapshot`` feature.


``out/``
--------

This directory encloses all the build results from commands run by the
toolkit.

.. admonition:: Watch out to the mount options of your current partition
   :class: warning

   Implementation detail: since the rootfs of the CLIP OS jails and targets are
   built within this directory, it must not be located on a filesystem mount
   point with options restricting filesystem features such as the creation of
   device nodes or the usage of executable files. In other words, options such
   as ``nodev``, ``noexec`` or ``nosuid`` **MUST NOT** be set on the underlying
   mount point of this directory.

The sub-directories in this folder will reflect the ``<product>/<recipe>/``
tree with separation with the version number.

``out/<product>/<version>/<recipe>/``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The output results for a given ``<recipe>`` of a specific ``<product>`` at
version ``<version>``.

.. admonition:: About the subdirectory ``root/`` below directories for the
                *build*, *image* and *configure* recipe actions
   :class: tip

   A specific ``root`` directory can be found under the directories dedicated
   to the *build*, *image* and *configure* recipe actions. This ``root``
   directory is the location where the respective recipe actions are working to
   build the rootfs.

   You need to be careful not to change any file or folder (including modes or
   ownerships) under that directory because those changes may end up in the
   final built image for the corresponding recipe. It might not be a good idea
   to apply changes directly in these ``root`` directories except for
   experimenting tweaks while debugging.

``out/<product>/<version>/<recipe>/bundle/``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The output result of the ``<recipe>`` recipe form ``<product>`` version
``<version>`` product. *Bundle* recipe action is often the last recipe action
and the only one to produce the tangible products (*e.g.* disk images, EFI
binary) rather than a complete rootfs directory.

``products/``
-------------

This directory holds the project main build and configuration steps in the
``clipos`` subfolder.

Each downstream project based on CLIP OS must create a directory here and
mirror part of the CLIP OS directory hierarchy.

.. admonition:: How to add a custom product?
   :class: tip

   Instructions on how to derive this project for your specific use case are
   available in the :ref:`derive` guide.

``products/clipos/``
~~~~~~~~~~~~~~~~~~~~

The recipes files in charge of spawning SDK containers making use of the
scripts below to build the sub-parts of CLIP OS and bundling them together in a
final image or set of installable images.

``products/clipos/doc/``
^^^^^^^^^^^^^^^^^^^^^^^^

This directory encloses all the documentation related to the CLIP OS project
(i.e., CLIP OS toolkit excluded).

``products/clipos/sdk/``
^^^^^^^^^^^^^^^^^^^^^^^^

The recipe describing the CLIP OS SDK used by all CLIP OS recipes.

``products/clipos/core/``
^^^^^^^^^^^^^^^^^^^^^^^^^

The recipe describing the CLIP OS *core* root filesystem.

``products/clipos/efiboot/``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The recipe describing the CLIP OS *EFI boot* items.

``run/``
--------

Runtime working directory for the ``cosmk`` toolkit and Python virtual
environment.

``src/``
--------

Anything under this directory is source code of third-party or in-house
projects.

``src/external/``
~~~~~~~~~~~~~~~~~

This directory encloses all the repositories of external upstream sources that
may receive patches specific to CLIP OS.

``src/external/linux/``
^^^^^^^^^^^^^^^^^^^^^^^

Upstream Linux kernel sources with our sets of patches in dedicated branches.

``src/external/systemd/``
^^^^^^^^^^^^^^^^^^^^^^^^^

Upstream systemd source code with both `systemd
<https://github.com/systemd/systemd>`_ and `systemd-stable
<https://github.com/systemd/systemd-stable>`_ code branches.

``src/platform/``
~~~~~~~~~~~~~~~~~

This directory encloses all the repositories of the in-house sub-projects which
are part of CLIP OS.

``src/portage/``
~~~~~~~~~~~~~~~~

This directory encloses all the Portage tree overlays exposed in the SDK.

.. admonition:: Third-party Portage tree overlays
   :class: tip

   Any potential third-party Portage tree overlays must be added here.

``src/portage/gentoo/``
^^^^^^^^^^^^^^^^^^^^^^^

The upstream Gentoo Portage tree.

``src/portage/clipos/``
^^^^^^^^^^^^^^^^^^^^^^^

The CLIP OS Portage tree overlay containing ``ebuild`` files, *eclasses*, and
Portage profiles that are specific to CLIP OS.

``toolkit/``
------------

The CLIP OS toolkit.

.. admonition:: Notable files
   :class: tip

   * ``repo_root.justfile``: The source tree root (symlinked in the source tree
     root) *justfile*.
   * ``source_me.sh``: The script to source to setup the Python virtualenv.

``tookit/cosmk/``
~~~~~~~~~~~~~~~~~~~~

The Python module used to setup and launch SDKs to build CLIP OS.

``tookit/doc/``
~~~~~~~~~~~~~~~

The toolkit documentation.

``tookit/docroot/``
~~~~~~~~~~~~~~~~~~~

The root and configuration files used to build the full CLIP OS documentation.

``tookit/qa/``
~~~~~~~~~~~~~~

Python tools and configuration used for QA for the ``cosmk`` module.

``tookit/repo-scripts/``
~~~~~~~~~~~~~~~~~~~~~~~~

Scripts used with the ``repo forall`` command to run specific actions depending
on context. Those scripts are usually calls by ``just`` recipes.

``tookit/scripts/``
~~~~~~~~~~~~~~~~~~~

Helpers scripts.

``justfile``
------------

The root ``Justfile`` with the often used commands and recipes to work on the
project and interact easily with the Git repositories.

.. admonition:: Origin of this file
   :class: tip

   This file is symlinked at the root of the source tree by the toolkit's
   ``source_me.sh``. It won't show up here until you have ``source``'d that
   specific file.

.. vim: set tw=79 ts=2 sts=2 sw=2 et:
