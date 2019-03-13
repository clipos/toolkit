.. Copyright © 2018 ANSSI.
   CLIP OS is a trademark of the French Republic.
   Content licensed under the Open License version 2.0 as published by Etalab
   (French task force for Open Data).

.. _setup:

Environment setup
=================

This document will walk you through the steps to setup the environment required
to use the tools in the CLIP OS project.

Global environment configuration requirements
---------------------------------------------

Here is a requirements check-list about your global environment:

1. You must run a **64-bit x86 system** (a.k.a. ``AMD64``, ``Intel 64`` or
   ``x86_64``) architecture.

   .. admonition:: About other system architectures...
      :class: tip

      Cross-compiling to other system architectures is not supported yet. No
      other host system architecture is supported yet.

2. You must run **Linux**. No other operating system is supported. Any
   relatively recent and stable kernel provided by a major Linux distribution
   should be compatible with the CLIP OS toolkit.

   .. admonition:: Supported Linux distributions
      :class: note

      The project has been tested and is known to work with the following
      distributions:

        * Arch Linux
        * Debian testing (*buster*) and Debian unstable
        * Fedora 28
        * Ubuntu 18.04

      Similarly, the following kernels are supported:

        * 4.16 and above (Arch Linux, Debian unstable, etc.)
        * 4.9 (Debian stable (*stretch*))

      The project will likely work on other distributions but we do not plan on
      supporting any other one yet.

   .. admonition:: About other Linux distributions...
      :class: tip

      Provided a kernel can support all the features used within the CLIP OS
      toolkit (such as namespaces, capabilities, cgroups for containerization,
      SquashFS, loop devices, OverlayFS, tmpfs, etc.), it is expected to work
      without issue.

3. Both your hardware and your kernel must support **KVM** (through Intel
   VT-x or AMD-V technologies) to run CLIP OS virtual machine images.

4. **Super-user privileges** are required on punctual occasions through the use
   of the ``sudo`` utility.

   .. admonition:: Why this requirement?
      :class: tip

      Super-user privileges are required to permit the CLIP OS toolkit to
      create and manage Linux containers, such as the CLIP OS SDK ephemeral
      containers.

      However, the CLIP OS toolkit will not run everything as root as it will
      lower its effective privileges when root privileges are not necessary.

      For more information, see the implementation of the class
      `clipostoolkit.cosmk.privileges.ElevatedPrivileges` in
      :ref:`cosmk-api`.

5. Make sure to have allocated a consequent size of **swap space** on your
   system as it might be required when working on large ephemeral SDK
   environments. Having a lot of RAM (16GB+) will also help.

   .. admonition:: Why this requirement?
      :class: tip

      SDK ephemeral containers make use of "in-memory" *tmpfs* OverlayFS
      layers. As a consequence, there are scenarios where memory usage may be
      large (typically when bootstrapping the CLIP OS SDK image) and may not
      fit the entire memory of the system.

6. Make sure to have **enough free storage space** before getting the source
   tree as it can take up to several gigabytes of storage, and even more when
   you will begin building CLIP OS images. 50GB should be a minimum.

7. Make sure to work in a **filesystem without any restricted features** such
   as `noexec` or `nodev` as it will cause undefined issues throughout the
   building process of some parts of the CLIP OS images.


Software dependencies
---------------------

.. admonition:: TL;DR
   :class: tip

   If your are using a distribution supported by the project, you may skip this
   part of the documentation and jump directly to the section
   :ref:`dependencies-installation-on-supported-linux-distributions`.
   Otherwise (or if you encounter issues with the above method), please
   continue reading this section.

To get a functional environment, you will need these software dependencies in
your userland:

- **Git** as all the source code is versioned through Git repositories.

- **repo** (tool from the Android Open Source Project) is required to fetch
  the source tree.

  .. admonition:: Alternative way to install *repo*
     :class: note

     ``repo`` might be packaged by your Linux distribution. Otherwise you may
     have to get it and install it from source. To do so, follow the related
     instructions on `the Android Open Source project page regarding the setup
     of the environment for AOSP
     <https://source.android.com/setup/build/downloading#installing-repo>`_.

- **Git LFS** (Git Large File Storage extension) is required to fetch Git
  repositories with a lot of large binary files.

  .. admonition:: Alternative way to install Git LFS
     :class: note

     If ``git-lfs`` is not provided through a package of your Linux
     distribution, you can follow instructions from the `Git LFS project pages
     <https://github.com/git-lfs/git-lfs/wiki/Installation>`_ to install it.

- **Python 3.6 (or later)** with a working C compiler and some basic
  development libraries and tools as well as the appropriate CPython C header
  files.

  .. admonition:: Why a C compilation infrastructure is needed on the host
                  while all the compilations are done within containers?
     :class: note

     These development packages are required to build some external Python
     packages vendored in the source tree and which embed some CPython code.

- **sudo** (v1.8.21 or above) is required to permit the CLIP OS toolkit to
  elevate privileges to super-user privileges. The current unprivileged user
  must be a ``sudoer`` to be able to gain those privileges *via* the use of
  ``sudo``.

- **runc** (the OCI runtime tool) is required as it is used as the runtime
  for the CLIP OS SDK Linux containers.

  .. admonition:: Alternative and more convenient way to get *runc* on your
                  system
     :class: tip

     Since *runc* is a project originated from Docker and used as a container
     runtime by the Docker engine (since version 1.11 of the Docker Engine),
     installing **the Docker Engine is an alternative** to provide the ``runc``
     utility to the CLIP OS toolkit (Docker embeds a ``runc`` binary under the
     name of ``docker-runc``).

     This tip may be useful if your distribution does not provide a standalone
     ``runc`` package but does provide a package for Docker.

- **squashfs-tools** and **util-linux** system packages for the use of
  ``mksquashfs`` and ``losetup`` system utilities.

  .. admonition:: Why SquashFS and loop devices?
     :class: note

     These two utilities are required to create and mount squashfs images used
     internally by the CLIP OS toolkit as the rootfs images of the ephemeral
     SDK containers.

- **Rust** language support to build `just <https://github.com/casey/just>`_.
  ``just`` is a simple command-line utility to launch and abstract sequences of
  shell commands within ``Justfiles``. These files follow a *Makefile*-like
  syntax and provide an alternative way (in the context of the CLIP OS toolkit)
  to launch build jobs and other source code management common scripts as the
  ``cosmk`` tool does not implement all the required features yet.

  .. admonition:: Alternative way to install Rust
     :class: note

     If Rust is not provided by any of your Linux distribution packages, you
     can install it with `rustup <https://rustup.rs/>`_.

- **Bash 4.1 (or later)** is required for some toolkit helper scripts.

- **libvirt with QEMU and KVM support** are required as the platform to run the
  CLIP OS virtual machines with QEMU with virtualized networks.

  .. admonition:: Avoid running QEMU as root if not necessary
     :class: tip

     On some Linux distributions (e.g., Arch Linux), libvirt is provided with a
     default configuration which runs QEMU as root. If you intend to use
     libvirt only for the purpose of running CLIP OS QEMU images, you may want
     to run the QEMU processes launched by libvirt as your current user.

     To do so, edit the file ``/etc/libvirt/qemu.conf`` and change the values
     for the ``user`` and ``group`` as follows:

     .. code-block:: guess

        user = "myusername"  # replace with your current username
        group = "kvm"

.. _dependencies-installation-on-supported-linux-distributions:

Dependencies installation on supported Linux-distributions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On Ubuntu or Debian 10 (testing) and unstable (with ``contrib`` sources enabled
for Debian):

.. code-block:: shell-session

   $ sudo apt install \
          python3 python3-dev python3-venv \
          gnupg2 repo git git-lfs openssh-client \
          build-essential pkg-config \
          runc sudo squashfs-tools \
          qemu libvirt-dev libvirt-daemon \
          virt-manager gir1.2-spiceclientglib-2.0 gir1.2-spiceclientgtk-3.0 \
          debootstrap \
          rustc cargo

On Fedora 28:

.. code-block:: shell-session

   $ sudo dnf install \
          python2 python3-devel \
          gnupg git git-lfs openssh-clients \
          @development-tools \
          runc sudo squashfs-tools \
          qemu libvirt-devel libvirt-daemon \
          virt-manager \
          debootstrap \
          rust cargo

On Arch Linux:

.. code-block:: shell-session

   $ sudo pacman -Syu \
         python \
         gnupg repo git git-lfs openssh \
         base-devel \
         runc sudo squashfs-tools \
         qemu libvirt bridge-utils dnsmasq \
         virt-manager ebtables \
         debootstrap debian-archive-keyring \
         rust


How to fetch the entire source tree?
------------------------------------

The project source tree is split among several distinct repositories that are
managed together using ``repo``.

.. admonition:: Make sure the Git LFS filters are enabled
   :class: important

   **Please ensure to have installed the Git LFS filters hooks for Git** either
   globally on your system (changes will be made in ``/etc/gitconfig``) with
   the following command:

   .. code-block:: shell-session

      $ sudo git-lfs install --system --skip-repo

   or only for your current user (changes will be made in ``~/.gitconfig``):

   .. code-block:: shell-session

      $ git-lfs install --skip-repo

   This step is required to be done before synchronizing the whole CLIP OS
   source tree and allows to automatically download the files stored within the
   Git LFS server when ``repo`` checks out the Git LFS-backed repositories of
   the source tree.

.. admonition:: Watch out for unusual *umask* values!
   :class: error

   Due to the fact that we bind-mount the source tree within SDK containers,
   **please ensure to fetch and synchronize the entire source tree with a umask
   value keeping permissions to read files and traverse directories**
   (recommended *umask* value ``0022``).

   Failure to do so may lead to undefined issues when using the CLIP OS toolkit
   as all the file modes of this source tree are left unchanged when they are
   exposed within SDK containers. As a consequence, some unprivileged programs
   running in these containers might encounter a "Permission denied" error when
   trying to read files whose mode deny access for "others".

Then to get the entire source tree:

.. code-block:: shell-session

   $ mkdir clipos
   $ cd clipos
   $ umask 0022
   $ git lfs install --skip-repo
   $ repo init -u https://github.com/CLIPOS/manifest
   $ repo sync

This may take some time (several minutes at least, but this depends on your
network bandwidth) as several Git repositories need to be cloned, including
large Git repositories holding lots of contents and history, such as the Linux
kernel (``src/external/linux/``) or the Gentoo Portage tree
(``src/portage/gentoo/``).

.. admonition:: Quicker synchronization
   :class: tip

   If you are certain to have set everything up correctly and if you are not
   intreseted in the output of the ``repo sync`` command, you can instruct
   *repo* to synchronize all the sub-repositories concurrently by using
   multiple Git processes:

   .. code-block:: shell-session

      $ repo sync -j4

   This should be significantly faster than the method above but the output of
   the Git cloning processes might be interlaced and not easily readable.

At this point, you should have successfully set up your environment and
fetched the whole source tree of the CLIP OS project.

.. admonition:: In case you forgot to install the Git LFS filters *before*
                synchronizing the whole source tree
   :class: note

   If you forgot to setup the Git LFS filter before running ``repo sync``, you
   can still download the missing contents of the files backed by Git LFS (and
   therefore fix your current source tree checkout) by running this command:

   .. code-block:: shell-session

      $ repo forall -c 'git lfs install && git lfs pull'

Congratulations, you are now ready to launch a :ref:`build of a CLIP OS image
<build>`.

.. vim: set tw=79 ts=2 sts=2 sw=2 et:
