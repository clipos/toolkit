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
to use all the CLIP OS tools required to build and conveniently manage the
source tree (such as ``just`` to handle the ``justfile``'s and ``cosmk``):

.. code-block:: shell-session

   $ source toolkit/source_me.sh
   (toolkit) $

Building the full project
-------------------------

You will then be able to use the ``justfile``'s to run commands to build CLIP
OS. Building the CLIP OS project requires multiple successive steps that are
described in `Justfiles <https://github.com/casey/just>`_. All commands are run
from the project root directory.

To list the available `just` recipes:

.. code-block:: shell-session

   (toolkit) $ just --list

To run all steps required to build CLIP OS:

.. code-block:: shell-session

   (toolkit) $ sujust all

.. important::

   As some tasks need root privileges to function properly you must pay
   attention to which ``just`` commands needs ``root`` privileges as there are
   other ``just`` commands (such as helpers for source repository and branch
   manipulation) which **do not** require ``root`` privileges.

.. note::

   On most distributions, the default configuration will reset the
   ``PATH`` environment variable set by the CLIP OS toolkit environment to a
   fixed default value when calling ``sudo``.

   To workaround this issue without modifying your ``sudoers`` configuration,
   the CLIP OS toolkit environment sets an alias for the sudo command to keep
   your current ``PATH``.

.. note::

   On some distributions (e.g., Debian), the default user ``$PATH`` variable
   does not include the ``/sbin`` and ``/usr/sbin`` folders. Please add those
   to your user ``$PATH``. For example:

   .. code-block:: shell-session

      $ export PATH="$PATH:/sbin:/usr/sbin"

Building a QEMU image and running using QEMU/KVM
------------------------------------------------

To build a QCOW2 QEMU disk image and to setup a EFI & QEMU/KVM enabled virtual
machine with ``libvirt``, use:

.. code-block:: shell-session

   (toolkit) $ sujust qemu

.. admonition:: Local login disabled by default
   :class: important

   The default build configuration will create production images with root
   access disabled. See the next paragraph for instructions to create an
   instrumented build.

.. admonition:: TPM support
   :class: important

   To test the TPM support, you need to install
   `libtpms <https://github.com/stefanberger/libtpms>`_ and
   `swtpm <https://github.com/stefanberger/swtpm>`_ using either instructions
   from the ``INSTALL`` file on their respective GitHub repositories or the AUR
   packages for Arch Linux users.

Instrumented build for testing
------------------------------

In order to test the QEMU images, you have to select the instrumentation level
you want by copying the ``toolkit/instrumentation.toml.example`` example in the
source tree root folder:

.. code-block:: shell-session

   (toolkit) $ cp toolkit/instrumentation.toml.example instrumentation.toml

The default instrumented configuration will enable you to log in as root
without password. You will have to rebuild the project and the QEMU image to
apply the change:

.. code-block:: shell-session

   (toolkit) $ sujust all
   (toolkit) $ sujust qemu

.. vim: set tw=79 ts=2 sts=2 sw=2 et:
