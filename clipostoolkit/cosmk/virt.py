# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright © 2017 ANSSI. All rights reserved.

"""This module manages all the code logic relative to the creation and
management of the CLIP OS virtualized environments with `libvirt`."""

import os
import pprint
import re
import shutil
import sys
from string import Template
from typing import Dict, Iterator, List, Optional, Tuple

import libvirt
import psutil

from . import log
from .commons import line, run
from .exceptions import CosmkEnvironmentError, VirtualizedEnvironmentError
from .privileges import ElevatedPrivileges
from .sourcetree import repo_root_path


def guess_external_netiface_name() -> str:
    """Tries to retrieve the name of the external network interface. To do so,
    this function select the first returned network interface whose name
    suggest to be an Ethernet or wireless interface (``en*``, ``eth*`` or
    ``wl*``) and which appears to be connected to a full-duplex medium.

    :raise VirtualizedEnvironmentError: if no external network inteface could
        be guessed and no dummy value has been provided

    """

    iface_name_pattern = re.compile(r'(en|eth|wl).*')
    if_stats: Dict[str, psutil._common.snicstats] = psutil.net_if_stats()
    for iface, stats in if_stats.items():
        if not iface_name_pattern.fullmatch(iface):
            continue
        if stats.duplex == psutil.NIC_DUPLEX_FULL:
            return iface
    else:
        raise VirtualizedEnvironmentError(line(
            """Could not guess any potential external network interface on
            the current system."""))


class VirtualizedEnvironment(object):
    """A CLIP OS recipe virtualized environment.

    :param name: the name to give to the libvirt domain and network
    :param libvirt_domain_xml_template: the path to the XML template file to
        use as the XML domain definition for the libvirt domain
    :param libvirt_network_xml_template: the path to the XML template file to
        use as the XML network definition for the libvirt network
    :param qcow2_main_disk_image: the path to the main disk image (formatted
        as QCOW2) to use for the libvirt domain to be created
    :param ovmf_firmware_code: the path to the OVMF firmware code to be
        used by the libvirt domain
    :param ovmf_firmware_vars_template: the path to the OVMF firmware
        UEFI vars template file to be used by the libvirt domain

    """

    # The runtime working directory: the location where the containers bundles
    # will be created and managed (to put it differently, this is our
    # /var/lib/docker...).
    RUNTIME_WORKING_DIR_REPO_SUBPATH = "run/virtual_machines"

    def __init__(self,
                 name: str,
                 libvirt_domain_xml_template: str,
                 libvirt_network_xml_template: str,
                 qcow2_main_disk_image: str,
                 ovmf_firmware_code: str,
                 ovmf_firmware_vars_template: str) -> None:
        # get a connection handle to the system libvirt daemon:
        with ElevatedPrivileges():
            self._conn = libvirt.open('qemu:///system')
        if not self._conn:
            raise VirtualizedEnvironmentError(line(
                """Could not connect to the system libvirt daemon
                ("qemu:///system")."""))
        log.debug("Sucessfully connected to \"qemu:///system\".")

        self.name = name
        emulator = "qemu-system-x86_64"
        emulator_binpath = shutil.which(emulator)
        if not emulator_binpath:
            raise VirtualizedEnvironmentError(line(
                """The specified emulator {!r} cannot be found on the current
                system.""").format(emulator))
        self.emulator_binpath = emulator_binpath
        self.qcow2_main_disk_image = qcow2_main_disk_image
        self.libvirt_domain_xml_template = libvirt_domain_xml_template
        self.libvirt_network_xml_template = libvirt_network_xml_template
        self.ovmf_firmware_code_filepath = ovmf_firmware_code
        self.ovmf_firmware_vars_template_filepath = ovmf_firmware_vars_template

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))


    def _populate_libvirt_domain_working_dir(self, working_dir: str) -> None:
        """Populate a given directory to be used as a working directory for the
        libvirt domain. This is made in order not to mess with the file serving
        to create the virtual machine (such as the main disk image or the UEFI
        vars file) and to ensure that all the changes that libvirt can bring to
        the underlying files of the virtualized environment are contained
        within this working directory.

        :param working_dir: the directory where the required files for the
            libvirt domain will be deployed and where libvirt will work

        """

        if not os.path.exists(working_dir):
            os.makedirs(working_dir)

        workdir_qcow2_image = os.path.join(working_dir, "main_disk.qcow2")
        try:
            shutil.copy(self.qcow2_main_disk_image, workdir_qcow2_image)
        except:
            raise VirtualizedEnvironmentError(line(
                """The specified QCOW2 image file ({!r}) for the virtual
                machine main disk could not be copied into the virtual machine
                working directory. Cannot create the virtualized
                environment.""").format(self.qcow2_main_disk_image))

        workdir_ovmf_code = os.path.join(working_dir, "OVMF_code.fd")
        try:
            shutil.copy(self.ovmf_firmware_code_filepath, workdir_ovmf_code)
        except:
            raise VirtualizedEnvironmentError(line(
                """The specified OVMF firmware code file ({!r}) could not be
                copied into the virtual machine working directory. Cannot
                create the virtualized environment.""")
                .format(self.ovmf_firmware_code_filepath))

        workdir_ovmf_vars_template = os.path.join(working_dir,
                                                  "OVMF_vars_template.fd")
        try:
            shutil.copy(self.ovmf_firmware_vars_template_filepath,
                        workdir_ovmf_vars_template)
        except:
            raise VirtualizedEnvironmentError(line(
                """The specified OVMF firmware UEFI variables template file
                ({!r}) could not be copied into the virtual machine working
                directory. Cannot create the virtualized environment.""")
                .format(self.ovmf_firmware_vars_template_filepath))

        # prepare the path to receive the OVMF UEFI vars file to be created
        # from the OVMF UEFI vars template file automatically by libvirt at the
        # first start of the domain
        workdir_ovmf_vars = os.path.join(working_dir, "OVMF_vars.fd")

        # create the libvirt domain and network XML files for the VM definition
        with open(self.libvirt_network_xml_template, 'r') as xmlfile:
            xmlcontents = xmlfile.read()
        xmltpl = Template(xmlcontents)
        try:
            external_iface = guess_external_netiface_name()
        except VirtualizedEnvironmentError:
            external_iface = 'nonguessable'
        network_name = self.name
        xmlnetwork = xmltpl.substitute(
            name=network_name,
            external_iface=external_iface,
        )
        workdir_network_xml = os.path.join(working_dir, "network.xml")
        with open(workdir_network_xml, "w+") as xmlfile:
            xmlfile.write(xmlnetwork)

        # Do we have a TPM emulator installed? (i.e. is swtpm in $PATH?)
        is_swtpm_usable = bool(shutil.which('swtpm'))
        tpm_support_xmlhunk = "<tpm model='tpm-tis'><backend type='emulator' version='2.0'></backend></tpm>"

        with open(self.libvirt_domain_xml_template, 'r') as xmlfile:
            xmlcontents = xmlfile.read()
        xmltpl = Template(xmlcontents)
        xmldomain = xmltpl.substitute(
            domain_name=self.name,
            ovmf_firmware_code_filepath=workdir_ovmf_code,
            ovmf_firmware_vars_filepath=workdir_ovmf_vars,
            ovmf_firmware_vars_template_filepath=workdir_ovmf_vars_template,
            qemu_x86_64_binpath=self.emulator_binpath,
            qcow2_main_disk_image_filepath=workdir_qcow2_image,
            network_name=network_name,
            tpm_support=(tpm_support_xmlhunk if is_swtpm_usable else ""),
        )
        workdir_domain_xml = os.path.join(working_dir, "domain.xml")
        with open(workdir_domain_xml, "w+") as xmlfile:
            xmlfile.write(xmldomain)

    def create(self,
               start: bool = False,
               destroy_preexisting: bool = False) -> None:
        """Create the virtualized environment in libvirt with its dedicated
        working directory in the sub-path in repo (defined in
        :py:data:`RUNTIME_WORKING_DIR_REPO_SUBPATH`)."""

        if destroy_preexisting:
            self.destroy()

        # check for no name collision with preexisting domains or networks:
        for domain in self._conn.listAllDomains():
            if domain.name() == self.name:
                raise VirtualizedEnvironmentError(line(
                    """A libvirt domain with the name {!r} already exists
                    within the system libvirt daemon and cannot be removed
                    (either because not requested or still active).""")
                    .format(self.name))
        for network in self._conn.listAllNetworks():
            if network.name() == self.name:
                raise VirtualizedEnvironmentError(line(
                    """A libvirt network with the name {!r} already exists
                    within the system libvirt daemon and cannot be removed
                    (either because not requested or still active).""")
                    .format(self.name))

        # the working dir to use
        working_dir = os.path.join(repo_root_path(),
                                   self.RUNTIME_WORKING_DIR_REPO_SUBPATH,
                                   self.name)
        if os.path.exists(working_dir):
            # obliterate directory unconditionnally as we may already have
            # destroyed the associated libvirt domain
            shutil.rmtree(working_dir)
        try:
            self._populate_libvirt_domain_working_dir(working_dir)

            network_xml_file = os.path.join(working_dir, "network.xml")
            with open(network_xml_file, 'r') as xmlfile:
                libvirt_network = self._conn.networkDefineXML(xmlfile.read())
            if not libvirt_network:
                raise VirtualizedEnvironmentError(line(
                    """Could not create the libvirt network from the network
                    XML file description ({!r}).""")
                    .format(network_xml_file))
            if start:
                libvirt_network.create()  # start the network

            domain_xml_file = os.path.join(working_dir, "domain.xml")
            with open(domain_xml_file, 'r') as xmlfile:
                libvirt_domain = self._conn.defineXML(xmlfile.read())
            if not libvirt_domain:
                raise VirtualizedEnvironmentError(line(
                    """Could not create the libvirt domain from the domain
                    XML file description ({!r}).""")
                    .format(domain_xml_file))
            if start:
                libvirt_domain.create()  # start the domain
        except:
            self.destroy()
            raise  # re-raise the exception just caught

    def spawn_virt_manager_console(self) -> None:
        """Spawn a virtual machine manager console for the virtual machine."""

        virt_manager_binpath = shutil.which("virt-manager")
        if not virt_manager_binpath:
            raise CosmkEnvironmentError(line(
                """\"virt-manager\" does not seem to be installed. Could not
                spawn a graphical console to the created {!r} virtual
                environment.""").format(self.name))
        # virt-manager is expected to fork into background, i.e. the small
        # timeout
        run([virt_manager_binpath, "--connect", "qemu:///system",
             "--show-domain-console", self.name], timeout=2, check=True)

    def destroy(self) -> None:
        """Destroy the virtualized environment in libvirt with its dedicated
        working directory in the sub-path in repo (defined in
        :py:data:`RUNTIME_WORKING_DIR_REPO_SUBPATH`)."""

        for domain in self._conn.listAllDomains():
            if domain.name() == self.name:
                if domain.isActive():
                    domain.destroy()
                domain.undefineFlags(
                    libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE |
                    libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA |
                    libvirt.VIR_DOMAIN_UNDEFINE_NVRAM
                )
                break
        for network in self._conn.listAllNetworks():
            if network.name() == self.name:
                if network.isActive():
                    network.destroy()
                network.undefine()
                break
        working_dir = os.path.join(repo_root_path(),
                                   self.RUNTIME_WORKING_DIR_REPO_SUBPATH,
                                   self.name)
        if os.path.exists(working_dir):
            shutil.rmtree(working_dir)
