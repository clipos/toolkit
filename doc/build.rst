.. Copyright © 2018 ANSSI.
   CLIP OS is a trademark of the French Republic.
   Content licensed under the Open License version 2.0 as published by Etalab
   (French task force for Open Data).

.. _build:

Building
========

.. admonition:: Before going further, ensure to get a functional build
                environment setup
   :class: important

   You must complete the :ref:`toolkit environment setup <setup>` before
   executing any command from this page.

Activate the toolkit environment
--------------------------------

Create and activate the CLIP OS toolkit environment in which you will be able
to use the cosmk Python module and its associated tools (such as the
``justfile``'s):

.. code-block:: shell-session

   $ source toolkit/source_me.sh
   (toolkit) $

You will then be able to use the ``justfile``'s to run commands to build CLIP
OS:

.. code-block:: shell-session

   (toolkit) $ sujust all

.. important::

   As some tasks need root privileges to function properly you must pay
   attention to which ``just`` commands needs ``root`` privileges as there are
   other ``just`` commands (such as helpers for source repository and branch
   manipulation) which **do not** require ``root`` privileges.

.. note::

   On most distributions, the default configuration will reset the
   ``PATH`` environment variable set by ``cosmk`` to a fixed default value
   when calling ``sudo``.

   To workaround this issue without modifying your ``sudoers`` configuration,
   the ``cosmk`` environment sets an alias for the sudo command to keep your
   current ``PATH``.

.. note::

   On some distributions (e.g., Debian), the default user ``$PATH`` variable
   does not include the ``/sbin`` and ``/usr/sbin`` folders. Please add those
   to your user ``$PATH``. For example:

   .. code-block:: shell-session

      $ export PATH="$PATH:/sbin:/usr/sbin"

Build steps
-----------

Building the CLIP OS project requires multiple successive steps that are
described in `Justfiles <https://github.com/casey/just>`_. All commands are run
from the project root directory.

To list the available `just` recipes:

.. code-block:: shell-session

   (toolkit) $ just --list

To run all steps required to build CLIP OS:

.. code-block:: shell-session

   (toolkit) $ sujust all

Building the documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~

The project documentation is built with Sphinx. The documentation sources are
split among three directories:

  * the documentation root and Sphinx configuration in ``toolkit/docroot``;
  * the source of the toolkit section of the documentation in
    ``toolkit/doc``;
  * and the source of the CLIP OS product documentation in
    ``products/clipos/doc``.

To build the documentation and to open it in your browser, run:

.. code-block:: shell-session

   (toolkit) $ just doc
   (toolkit) $ just open-doc

Caching and binary packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To speed up the build process during development, we keep the output of each
build action in the ``cache`` and ``out`` folders. The ``cache`` directory
keeps binary packages and SDK images. The ``cache`` directory keeps the
intermediate rootfs, logs and temporary files that are safe to remove before a
rebuild.

By default, the build commands will clear their ``out`` folder and reuse cached
output (mainly packages) to speedup iterative development builds. To restart
everything from scratch:

.. code-block:: shell-session

   (toolkit) $ sujust clean
   (toolkit) $ sujust clean-cache
   (toolkit) $ sujust all

.. admonition:: Pre-built binary packages by a continuous integration
                infrastructure
   :class: note

   As of 20th September 2018, we are still working on the deployment of a
   continuous integration infrastructure which will provide pre-built binary
   packages to speed up day-to-day work on the developer's workstations. Once
   this CI infrastructure will be deployed, some commands will be made
   available to fetch those CI-built binary packages directly into the
   appropriate ``cache/`` subdirectories.

SDK
~~~

To build the software components of CLIP OS, we use a SDK based on Gentoo
Hardened. The SDK container is created by importing the upstream `stage 3 root
filesystem <https://wiki.gentoo.org/wiki/Stage_tarball#Stage_3>`_ and updating
it with a current copy of the upstream Gentoo Portage tree to include various
utilities. If unavailable, the SDK is automatically build, and may be manually
rebuild from scratch using:

.. code-block:: shell-session

   (toolkit) $ sujust products/clipos/sdk/bootstrap-from-sratch

Core
~~~~

The main rootfs in CLIP OS is called Core, and can be built using:

.. code-block:: shell-session

   (toolkit) $ sujust products/clipos/core

EFI boot partition
~~~~~~~~~~~~~~~~~~

EFI boot is the only supported boot method. The content of the EFI boot
partition (bootloader, kernel image, etc.) is built using:

.. code-block:: shell-session

   (toolkit) $ sujust products/clipos/efiboot

QEMU image & Debian SDK
~~~~~~~~~~~~~~~~~~~~~~~

In order to test the resulting OS, we use ``libguestfs`` tools to assemble a
QEMU qcow2 disk image to boot inside a EFI enabled virtual machine using
``libvirt``.

Similarly to the Gentoo Hardened based SDK, the Debian SDK is automatically
built, and may be manually rebuilt from scratch using:

.. code-block:: shell-session

   (toolkit) $ sujust products/clipos/sdk_debian/bootstrap-from-scratch

The qcow2 QEMU image may then be assembled using:

.. code-block:: shell-session

   (toolkit) $ sujust products/clipos/qemu/bundle

Testing the QEMU image
----------------------

To setup a EFI & QEMU/KVM enabled virtual machine with ``libvirt``, use:

.. code-block:: shell-session

   (toolkit) $ sujust products/clipos/qemu/run

Instrumented build for testing
------------------------------

The default build configuration will create production images with root access
disabled. In order to test the QEMU images, you have to select the
instrumentation level you want by copying the
``toolkit/instrumentation.toml.example`` example in the source tree root
folder:

.. code-block:: shell-session

   (toolkit) $ cp toolkit/instrumentation.toml.example instrumentation.toml

The default instrumented configuration will enable you to log as root in
without password. You will have to rebuild the project and the QEMU image to
apply the change:

.. code-block:: shell-session

   (toolkit) $ sujust all
   (toolkit) $ sujust qemu

.. vim: set tw=79 ts=2 sts=2 sw=2 et:
