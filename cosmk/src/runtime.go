package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"os/user"
	"path"
	"strings"
)

var runtime containerRuntime

type containerRuntime struct {
	Cmd  string
	Sudo bool
}

// Figure out which container runtime to use between:
// * rootless podman
// * privileged podman
// * Docker
func findContainerRuntime() {
	path, err := exec.LookPath("podman")
	if err == nil {
		Debug.Println("Found 'podman' at ", path)
		runtime = containerRuntime{Cmd: "podman", Sudo: true}

		// Are subuids configured? (Required for rootless)
		file, err := os.Open("/etc/subuid")
		if err != nil {
			return
		}
		defer file.Close()

		user, err := user.Current()
		if err != nil {
			return
		}
		username := user.Username

		scanner := bufio.NewScanner(file)
		for scanner.Scan() {
			split := strings.Split(scanner.Text(), ":")
			if len(split) != 0 && split[0] == username {
				runtime.Sudo = false
				return
			}
		}

		// Did not find any subuid for our current username. Running as root with sudo
		return
	}

	path, err = exec.LookPath("docker")
	if err == nil {
		Debug.Println("Found 'docker' at ", path)
		runtime = containerRuntime{Cmd: "docker", Sudo: true}
		return
	}

	Error.Fatalln("Could not find either 'podman' or 'docker in path!")
	runtime = containerRuntime{Cmd: "false", Sudo: false}
}

func (cr *containerRuntime) findCiImage(name string, version string) error {
	image := fmt.Sprintf("%s/%s:%s", rootConfig.Ci.Registry, name, version)
	Debug.Printf("Looking for image '%s' in local registry", image)

	cmd := cr.command()
	cmd.Args = append(cmd.Args, "inspect", image)
	err := cmd.Run()
	if err == nil {
		Debug.Printf("Found image '%s' in local registry", image)
		return nil
	}

	Info.Printf("Could not find image '%s' in local registry", image)

	return cr.pullImageFromCi(name, version)
}

func (cr *containerRuntime) findLocalImage(name string, version string) error {
	image := fmt.Sprintf("%s/%s:%s", "localhost", name, version)
	Debug.Printf("Looking for image '%s' in local registry", image)

	cmd := cr.command()
	cmd.Args = append(cmd.Args, "inspect", image)
	err := cmd.Run()
	if err == nil {
		Debug.Printf("Found image '%s' in local registry", image)
		return nil
	}

	Error.Printf("Could not find image '%s' in local registry", image)
	return err
}

func (cr *containerRuntime) pullImageFromCi(name string, version string) error {
	Info.Printf("Pulling image '%s:%s' from '%s'", name, version, rootConfig.Ci.Registry)
	cmd := cr.command()
	cmd.Args = append(cmd.Args, "pull", fmt.Sprintf("%s/%s:%s", rootConfig.Ci.Registry, name, version))
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err := cmd.Run()
	if err != nil {
		Info.Printf("Could not pull '%s:%s' from '%s'", name, version, rootConfig.Ci.Registry)
		return err
	}
	Info.Printf("Pulled image '%s:%s' from '%s'", name, version, rootConfig.Ci.Registry)
	return nil
}

func (cr *containerRuntime) command() *exec.Cmd {
	var cmd *exec.Cmd
	if cr.Sudo {
		cmd = exec.Command("sudo")
		cmd.Args = []string{"sudo", cr.Cmd}

	} else {
		cmd = exec.Command(runtime.Cmd)
		cmd.Args = []string{cr.Cmd}
	}
	return cmd
}

func (cr *containerRuntime) run(image string, command []string, action string, s *sdk, r *recipe) error {
	cmd := cr.command()
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	cmd.Args = append(cmd.Args, "run")

	// Disable SELinux confinement to enable access to home directory content
	cmd.Args = append(cmd.Args, "--security-opt", "label=disable")

	cmd.Args = append(cmd.Args, "--tty", "--interactive")
	cmd.Args = append(cmd.Args, "--tmpfs", "/tmp:rw,exec,nodev,nosuid")
	cmd.Args = append(cmd.Args, "--tmpfs", "/var/tmp:rw,exec,dev,suid")

	cmd.Args = append(cmd.Args, "--workdir", fmt.Sprintf("/mnt/products/%s/%s", s.Product.Short_name, s.Name))

	var recipeName string
	if r != nil {
		recipeName = r.Name
	} else {
		recipeName = s.Name
	}

	cmd.Args = append(cmd.Args, "--name", fmt.Sprintf("%s_%s.%s.working", s.Product.Short_name, recipeName, action))
	cmd.Args = append(cmd.Args, "--hostname", fmt.Sprintf("%s-%s", s.Product.Short_name, recipeName))

	cmd.Args = append(cmd.Args, "--env", fmt.Sprintf("COSMK_ACTION=%s", action))
	cmd.Args = append(cmd.Args, "--env", fmt.Sprintf("COSMK_RECIPE=%s", recipeName))

	// Ignore instrumentation features during SDK bootstrap to avoid hardcoding them in the image.
	if action != "bootstrap" {
		cmd.Args = append(cmd.Args, rootConfig.env()...)
	}
	cmd.Args = append(cmd.Args, s.Product.env()...)
	cmd.Args = append(cmd.Args, s.env()...)
	if r != nil {
		cmd.Args = append(cmd.Args, r.env()...)
	}

	if action == "run" {
		cmd.Args = append(cmd.Args, "--volume", fmt.Sprintf("%s:/mnt:rw", repoRootPath))
	} else {
		cmd.Args = append(cmd.Args, "--volume", fmt.Sprintf("%s:/mnt:ro", repoRootPath))
	}

	// Mount 'out' and 'cache' folder read-write
	for _, p := range []string{"out", "cache"} {
		pathHost := path.Join(repoRootPath, p, s.Product.Short_name, s.Product.Version, recipeName, action)
		pathSdk := path.Join("/mnt", p, s.Product.Short_name, s.Product.Version, recipeName, action)
		// Always start with an empty 'out' folder
		if p == "out" {
			os.RemoveAll(pathHost)
		}
		os.MkdirAll(pathHost, 0755)
		cmd.Args = append(cmd.Args, "--volume", fmt.Sprintf("%s:%s:rw", pathHost, pathSdk))
	}

	// Additional capabilities and writable directory for 'build' & 'bootstrap' actions
	if action == "bootstrap" || action == "build" {
		for _, dir := range s.Build.Writable_assets {
			distfilesHost := path.Join(repoRootPath, "assets", dir)
			distfilesSdk := path.Join("/mnt", "assets", dir)
			cmd.Args = append(cmd.Args, "--volume", fmt.Sprintf("%s:%s:rw", distfilesHost, distfilesSdk))
		}

		binpkgHost := path.Join(repoRootPath, "cache", s.Product.Short_name, s.Product.Version, recipeName, "binpkgs")
		binpkgSdk := path.Join("/mnt", "cache", s.Product.Short_name, s.Product.Version, recipeName, "binpkgs")
		os.MkdirAll(binpkgHost, 0755)
		cmd.Args = append(cmd.Args, "--volume", fmt.Sprintf("%s:%s:rw", binpkgHost, binpkgSdk))

		for _, v := range s.Build.Capabilities {
			cmd.Args = append(cmd.Args, "--cap-add", v)
		}
	}

	// Network access is disabled by default. It can be re-enabled during
	// development for 'bootstrap', 'build' and 'run' actions.
	if rootConfig.Development.Network != "yes" {
		cmd.Args = append(cmd.Args, "--network=none")
	} else if !(action == "bootstrap" || action == "build" || action == "run") {
		cmd.Args = append(cmd.Args, "--network=none")
	}

	// Keep the resulting container image only for the 'bootstrap' action
	if action != "bootstrap" {
		cmd.Args = append(cmd.Args, "--rm")
	}

	cmd.Args = append(cmd.Args, image)
	cmd.Args = append(cmd.Args, command...)

	Debug.Printf("Will run: %s", cmd.Args)

	err := cmd.Run()
	if err != nil {
		Error.Printf("SDK exited with error code: %s", err)
	}
	return err
}
