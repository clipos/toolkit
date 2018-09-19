# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017-2018 ANSSI. All rights reserved.

"""Module providing functions and classes to handle OCI Linux containers with
``runc``."""

import contextlib
import json
import os
import pprint
import re
import shutil
import stat
import sys
import tempfile
from typing import (IO, Any, AnyStr, Dict, Iterable, Iterator, List, Optional,
                    Set, Tuple, Union)

from .commons import linux_version, run
from .exceptions import (CosmkEnvironmentError, ContainerSnapshotError,
                         SystemCommandError)
from .fs import OverlayfsMount, SquashfsMount, TmpfsMount, mksquashfs
from .log import critical, debug, error, info, warn
from .sourcetree import repo_root_path

# Typing annotations
# Disabled because mypy do not support yet recursive types :(
#RuncJsonConfig = Dict[str, 'RuncJsonConfigItem']
#RuncJsonConfigItem = Union[str, int, RuncJsonConfig, List[RuncJsonConfig]]
RuncJsonConfig = Dict[str, Any]
RuncJsonConfigItem = Any


class Container(object):
    """Overly-simplified Linux OCI container abstraction with wrappers around
    the ``runc`` runtime for the command execution methods.

    :param name: the name of the container
    :param rootfs: the path to the rootfs squashfs image file
    :param hostname: the hostname within the container (defaults to the
        container name if set to :py:data:`None`)
    :param readonly_root: whether or not the rootfs shall be read-only mounted
    :param shared_host_netns: whether or not the container shall share the
        network namespace of the host in order to have networking access (to
        prevent having the hassle to configure IP routing and filtering on the
        host for this container)

    .. note::
        Eventhough this abstraction can be used independently outside of
        ``cosmk`` context, this class (and this module in a greater extent)
        is primarily intended to be used by the CLIP OS SDK abstraction to
        produce ephemeral containers (*i.e.* container sessions with their
        rootfs meant to be destroyed on closing, with still the possibility of
        being snapshotted into a reusable container squashfs image).

    """

    # OCI specs version this class tries to partially implement
    OCI_SPECS_VERSION = (1, 0, 0)

    # The runtime working directory: the location where the containers bundles
    # will be created and managed (to put it differently, this is our
    # /var/lib/docker...).
    RUNTIME_WORKING_DIR_REPO_SUBPATH = "run/containers"

    def __init__(self,
                 name: str,
                 rootfs: str,
                 hostname: Optional[str] = None,
                 readonly_root: bool = False,
                 shared_host_netns: bool = False) -> None:
        if not re.match(r'^[a-zA-Z0-9\.\_\-]+$', name):
            raise ValueError("container name is invalid")
        self.name = name
        self.rootfs = rootfs
        self.readonly_root = readonly_root
        self.hostname = hostname if hostname else name
        self.shared_host_netns = bool(shared_host_netns)
        # Add the basic POSIX capabilities to the container. This list comes
        # from the Docker default capabilities given to Docker containers (less
        # the ``CAP_NET_*`` ones to prevent doing naughty stuff with the
        # network in case we share the same netns as the host).
        self.capabilities = {
            "CAP_CHOWN",
            "CAP_DAC_OVERRIDE",
            "CAP_FSETID",
            "CAP_FOWNER",
            "CAP_MKNOD",
            "CAP_SETGID",
            "CAP_SETUID",
            "CAP_SETFCAP",
            "CAP_SETPCAP",
            "CAP_SYS_CHROOT",
            "CAP_KILL",
            "CAP_AUDIT_WRITE",
        }
        self.additional_mountpoints: List[ContainerMountpoint] = list()
        self.device_bindings: List[ContainerDeviceBinding] = list()

        # The default environment for container run sessions:
        self.default_env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "TERM": "xterm",
        }

    @property
    def unshared_namespaces(self) -> Set[str]:
        # follows nomenclature of the OCI specification not the kernel one
        return set(
            ["pid", "ipc", "uts", "mount"]
            + (["network"] if not self.shared_host_netns else [])
        )

    @property
    def mountpoints(self) -> List["ContainerMountpoint"]:
        """This list does not include the root mountpoint."""
        return self.additional_mountpoints + self.required_mountpoints

    @property
    def required_mountpoints(self) -> List["ContainerMountpoint"]:
        """The usual required default system mountpoints (*e.g.* ``/proc``,
        ``/dev``, etc.) for the container to run properly."""

        # This list comes from `runc spec` execution:
        return [
            ContainerMountpoint(
                source="proc",
                target="/proc",
                type="proc"
            ),
            ContainerMountpoint(
                source="tmpfs",
                target="/dev",
                type="tmpfs",
                options=["nosuid", "strictatime", "mode=755", "size=65536k"]
            ),
            ContainerMountpoint(
                source="devpts",
                target="/dev/pts",
                type="devpts",
                options=["nosuid", "noexec", "newinstance", "ptmxmode=0666",
                         "mode=0620", "gid=5"]
            ),
            ContainerMountpoint(
                source="shm",
                target="/dev/shm",
                type="tmpfs",
                options=["nosuid", "noexec", "nodev", "mode=1777",
                         "size=65536k"]
            ),
            ContainerMountpoint(
                source="mqueue",
                target="/dev/mqueue",
                type="mqueue",
                options=["nosuid", "noexec", "nodev"]
            ),
            ContainerMountpoint(
                source="sysfs",
                target="/sys",
                type="sysfs",
                options=["nosuid", "noexec", "nodev", "ro"]
            ),
            ContainerMountpoint(
                source="cgroup",
                target="/sys/fs/cgroup",
                type="cgroup",
                options=["nosuid", "noexec", "nodev", "relatime", "ro"]
            )
        ]

    def _runc_config(self,
                     command: List[str],
                     env: Dict[str, str],
                     cwd: str,
                     terminal: bool,
                     user: Tuple[int,int]) -> RuncJsonConfig:
        """Format this container as a ready-to-be-JSON-ified dict object to be
        fed to the ``runc`` runtime."""

        # reading advice:
        # https://github.com/opencontainers/runtime-spec/blob/master/config.md
        return {
            "ociVersion": ".".join(map(str, self.OCI_SPECS_VERSION)),
            "process": {
                "terminal": terminal,
                "user": {
                    "uid": user[0],
                    "gid": user[1],
                },
                "args": command,
                "env": ["{var}={contents}".format(var=k, contents=v)
                        for k,v in env.items()],
                "cwd": cwd,
                "capabilities": {
                    "bounding": list(self.capabilities),
                    "effective": list(self.capabilities),
                    "inheritable": list(self.capabilities),
                    "permitted": list(self.capabilities),
                    "ambiant": list(self.capabilities),
                },
                "rlimits": [ # TODO: abstract this?
                    {
                        "type": "RLIMIT_NOFILE",
                        "hard": 4096,
                        "soft": 4096,
                    }
                ],
                "noNewPrivileges": True,
            },
            "root": {
                "path": "rootfs",
                "readonly": False,
            },
            "hostname": self.hostname,
            "mounts": [mntpoint.as_dict() for mntpoint in self.mountpoints],
            "linux": {
                "devices": [devbind.as_dict() for devbind in
                            self.device_bindings],
                "resources": {
                    "devices": [
                        # restrict everything in the devices cgroup...
                            {"allow": False, "access": "rwm"}
                        ] + [
                        # except for the devices bindings we want to create
                            devbind.cgroup_authorization_dict()
                            for devbind in self.device_bindings
                    ],
                },
                "namespaces": [
                    {"type": ns} for ns in self.unshared_namespaces
                ],
                "maskedPaths": [  # TODO: investigate if more is needed
                    "/proc/kcore",
                    "/proc/latency_stats",
                    "/proc/timer_list",
                    "/proc/timer_stats",
                    "/proc/sched_debug",
                    "/sys/firmware",
                    "/proc/scsi"
                ],
                "readonlyPaths": [  # TODO: investigate if more is needed
                    "/proc/asound",
                    "/proc/bus",
                    "/proc/fs",
                    "/proc/irq",
                    "/proc/sys",
                    "/proc/sysrq-trigger"
                ]
            }
        }

    @contextlib.contextmanager
    def session(self) -> Iterator["ContainerSession"]:
        """Creates a session from this container in order to be able to call
        multiple commands on the same container instance and/or snapshotting
        the container contents into a squashfs image reusable by the
        `Container` class for future usage.

        This context manager is in charge of creating the runc bundle as a
        temporary directory ("temporary" meaning that its existence will be
        limited to the time span where the context manager is opened).
        This context manager has also the responsibility of mounting the
        container root filesystem (from its base squashfs image) in the
        suitable directory.

        """

        # create the default environment working dir if not existing:
        runtime_working_path = os.path.join(
            repo_root_path(), self.RUNTIME_WORKING_DIR_REPO_SUBPATH)
        if not os.path.exists(runtime_working_path):
            os.makedirs(runtime_working_path)

        # Create our bundle dir
        tmp_bundle_dir = tempfile.TemporaryDirectory(
            dir=runtime_working_path,
            prefix="{container_name}.".format(container_name=self.name))
        with tmp_bundle_dir as bundle_dir:
            # profit from the fact that tempfile.TemporaryDirectory has
            # generated a unique name for our container bundle that can be
            # given to the "runc run" command to name this container instance
            runc_container_name = os.path.basename(bundle_dir)

            # create the directory that will be receiving the rootfs mountpoint
            rootfs_dir = os.path.join(bundle_dir, "rootfs")
            os.mkdir(rootfs_dir)

            if self.readonly_root:
                with SquashfsMount(squashfile=self.rootfs,
                                   mountpoint=rootfs_dir):
                    yield ContainerSession(
                        container=self, bundle_dir=bundle_dir,
                        runc_container_name=runc_container_name)

            else:
                overlayfs_dir = os.path.join(bundle_dir, "overlay")
                os.mkdir(overlayfs_dir)
                overlayfs_lower_dir = os.path.join(overlayfs_dir, "lower")
                os.mkdir(overlayfs_lower_dir)
                overlayfs_tmpfs_dir = os.path.join(overlayfs_dir, "tmpfs")
                os.mkdir(overlayfs_tmpfs_dir)

                with SquashfsMount(squashfile=self.rootfs,
                                   mountpoint=overlayfs_lower_dir), \
                        TmpfsMount(overlayfs_tmpfs_dir, size="10g"):
                    overlayfs_upper_dir = os.path.join(overlayfs_tmpfs_dir,
                                                    "upper")
                    os.mkdir(overlayfs_upper_dir)
                    overlayfs_work_dir = os.path.join(overlayfs_tmpfs_dir,
                                                      "work")
                    os.mkdir(overlayfs_work_dir)

                    # Since the lowerdir underlying filesystem is a squashfs
                    # and does not support file handles, the overlayfs module
                    # raise a warning in the kernel message logs.
                    # For this reason, we disable the file indexing and NFS
                    # exportation capability for this overlayfs mountpoint. But
                    # to do so, we need to check the kernel version, otherwise
                    # the mount call will miserably fail with an error telling
                    # that the overlayfs module does not recognize one of the
                    # options:
                    overlayfs_mount_options: List[str] = []
                    if linux_version() >= (4, 13):
                        overlayfs_mount_options.append("index=off")
                    if linux_version() >= (4, 16):
                        overlayfs_mount_options.append("nfs_export=off")
                    with OverlayfsMount(mergeddir=rootfs_dir,
                                        lowerdir=overlayfs_lower_dir,
                                        upperdir=overlayfs_upper_dir,
                                        workdir=overlayfs_work_dir,
                                        options=overlayfs_mount_options):
                        if (self.shared_host_netns and
                               os.path.exists("/etc/resolv.conf")):
                            shutil.copy("/etc/resolv.conf",
                                        os.path.join(rootfs_dir,
                                                     "etc/resolv.conf"))

                        yield ContainerSession(
                            container=self, bundle_dir=bundle_dir,
                            runc_container_name=runc_container_name)

    def run(self, *args: Any, **kwargs: Any) -> None:
        """Shortcut function to run a single command in this container (a
        session will be instanciated temporarily just for this command)."""

        # identify the name of the runc binary
        with self.session() as sess:
            sess.run(*args, **kwargs)


class ContainerSession(object):
    """Session of a container instance."""

    def __init__(self,
                 container: Container,
                 bundle_dir: str,
                 runc_container_name: str) -> None:
        self.container = container
        self.bundle_dir = bundle_dir
        self.runc_container_name = runc_container_name

    def run(self,
            command: List[str],
            cwd: str="/",
            env: Optional[Dict[str, str]] = None,
            terminal: bool = False,
            user: Tuple[int,int]=(0, 0),
            stdout: Optional[IO[AnyStr]] = None,
            stderr: Optional[IO[AnyStr]] = None) -> None:
        """Run a command in this container session.

        :param command: the command to run (command line splitted into a list
            in the manner of the ``argv`` argument of the traditional
            ``execve(2)`` syscall)
        :param cwd: the current working directory
        :param env: the environment variable set
        :param terminal: hook the current TTY to the container if ``True``
        :param user: UID and GID couple values to use for the process run in
            the container
        :param stdout: facultative stream object able to receive for writing
            the standard output of the process run in the container
        :param stderr: facultative stream object able to receive for writing
            the standard error output of the process run in the container

        """

        # Apply the default environment variables set on the environment
        # variable set provided to this function (with priority on the values
        # defined in this one):
        default_env_copy = self.container.default_env.copy()
        default_env_copy.update(env if env else {})
        env = default_env_copy

        # identify the name of the runc binary
        if shutil.which("runc"):
            runc_bin = "runc"
        elif shutil.which("docker-runc"):
            runc_bin = "docker-runc"
        else:
            raise CosmkEnvironmentError(
                "cannot found 'runc' or 'docker-runc' binary")
        debug("runc binary path: {!r}".format(runc_bin))

        # generate the runc config for this command run as a dict...
        runc_config = self.container._runc_config(command=command,
                                                  env=env,
                                                  cwd=cwd,
                                                  terminal=terminal,
                                                  user=user)
        # ...and JSON-ify this dict in the suitable file for runc:
        debug("runc configuration dict to be JSON-ified:\n{}"
              .format(pprint.pformat(runc_config)))
        with open(os.path.join(self.bundle_dir, "config.json"), "w") as fjson:
            json.dump(runc_config, fjson, allow_nan=False, indent=2)

        runc_cmd = [runc_bin, "run", "--bundle", self.bundle_dir,
                    self.runc_container_name]
        if terminal:
            run(runc_cmd, check=True, terminal=True)
        else:
            run(runc_cmd, check=True, stdout=sys.stdout, stderr=sys.stderr)

    def snapshot(self, squashfs_filepath: str) -> None:
        """Snapshot the rootfs of this container"""

        if self.container.readonly_root:
            raise ContainerSnapshotError(
                "Underlying container has a readonly rootfs. What do you "
                "expect to be different from the image that originated this "
                "container?")

        try:
            mksquashfs(squashfs_file=squashfs_filepath,
                       source_dir=os.path.join(self.bundle_dir, "rootfs"),
                       compressor="gzip",
                       store_xattrs=True,
                       detect_sparse_files=True,
                       find_duplicates=True)
        except:
            raise ContainerSnapshotError(
                "could not produce a squashfs image file from the rootfs of "
                "this container session")


class ContainerMountpoint(object):
    """Mountpoint for a container (with the destination path within the
    container rootfs) that can be output as a dict for the runc JSON spec."""

    def __init__(self,
                 source: str,
                 target: str,
                 type: Optional[str] = None,
                 options: Optional[List[str]] = None) -> None:
        # Note: source is not always a path to a device or an existing fs node
        # (e.g. "overlayfs" dummy source value)
        self.source = source
        if os.path.abspath(target) != target:
            raise ValueError("target must be an absolute and normalized path")
        self.target = target
        self.type = type
        if options and any(("," in x for x in options)):
            raise ValueError(
                "A mount option contains a comma which serves as a separator "
                "for the mount options in the underlying mount command. "
                "Therefore, it cannot be used as part of any mount option.")
        self.options = options

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))

    def __str__(self) -> str:
        return repr(self)

    def as_dict(self) -> RuncJsonConfigItem:
        """Return this container mountpoint as a dict ready to be JSON-ified
        for the runc ``config.json`` specification."""

        d: Dict[str, Union[str, List[str]]] = {
            "source": self.source, "destination": self.target
        }
        if self.type:
            d.update({"type": self.type})
        if self.options:
            d.update({"options": self.options})
        return d


class ContainerDeviceBinding(object):
    """Device node binding for a container that can be output as a dict for the
    runc JSON spec.

    .. note::
       The OCI runtime automatically provides these devices nodes:
       ``/dev/null``, ``/dev/zero``, ``/dev/full``, ``/dev/random``,
       ``/dev/urandom``, ``/dev/tty``, ``/dev/console``, ``/dev/ptmx``.
       Therefore, there is no need to specify them.
       See: <https://github.com/opencontainers/runtime-spec/blob/master/config-linux.md#default-devices>_

    """

    def __init__(self,
                 host_device: str,
                 container_device: Optional[str] = None) -> None:
        """
        .. note::
           ``host_device`` MUST exist on the host and the binding in the
           container will be made with the same stat information (with
           exceptions to the ``can_read``, ``can_write`` and ``can_mknod``)

        .. todo::
           implement knobs to be able to restrict file modes on the binding
        """

        # interesting read:
        # https://github.com/opencontainers/runtime-spec/blob/master/config-linux.md#devices
        if os.path.abspath(host_device) != host_device:
            raise ValueError(
                "host_device must be an absolute and normalized path")
        self.host_device = host_device
        if (container_device and
                os.path.abspath(container_device) != container_device):
            raise ValueError(
                "container_device must be an absolute and normalized path")
        # assume the same abspath as the host if omitted from args
        self.container_device = (container_device if container_device else
                                 self.host_device)

        debug("identifying properties of device {!r} to bind it in a "
              "container".format(self.host_device))
        devstat = os.lstat(self.host_device)  # lstat don't follow symlinks
        if stat.S_ISCHR(devstat.st_mode):
            self.device_type = "c"  # char device
        elif stat.S_ISBLK(devstat.st_mode):
            self.device_type = "b"  # block device
        else:
            raise ValueError(
                "host_device must be a path to a host device node")
        self.device_major = os.major(devstat.st_rdev)
        self.device_minor = os.minor(devstat.st_rdev)
        self.filemode = stat.S_IMODE(devstat.st_mode)
        self.uid = devstat.st_uid
        self.gid = devstat.st_gid

    def __repr__(self) -> str:
        public_attrs = [x for x in vars(self).keys() if not x.startswith("_")]
        return "<{classname}: {public_attrs}>".format(
            classname=self.__class__.__name__,
            public_attrs=", ".join(["{k}={v!r}".format(k=k, v=getattr(self, k))
                                    for k in public_attrs]))

    def __str__(self) -> str:
        return repr(self)

    def as_dict(self) -> RuncJsonConfigItem:
        """Return this container device binding as a dict ready to be
        JSON-ified for the runc ``config.json`` specification."""

        return {
            "path": self.container_device,
            "type": self.device_type,
            "major": self.device_major,
            "minor": self.device_minor,
            "fileMode": self.filemode,
            "uid": self.uid,
            "gid": self.gid,
        }

    def cgroup_authorization_dict(self) -> RuncJsonConfigItem:
        """Return the device cgroup authorization dict structure ready to be
        JSON-ified for the runc ``config.json`` specification."""

        return {
            "allow": True,
            "type": self.device_type,
            "major": self.device_major,
            "minor": self.device_minor,
            "access": "rwm",
        }
