package main

import (
	"os"
	"os/exec"
	"path"
)

func doTestbedSetup() {
	docsDir := path.Join(repoRootPath, "testbed")
	err := os.Chdir(docsDir)
	if err != nil {
		Error.Fatalf("Could not chdir to '%s': %s", docsDir, err)
	}

	command := "./setup_testbed.sh"
	cmd := exec.Command(command)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Running '%s' failed with: %s", command, err)
	}
}

func doTestbedRun() {
	docsDir := path.Join(repoRootPath, "testbed")
	err := os.Chdir(docsDir)
	if err != nil {
		Error.Fatalf("Could not chdir to '%s': %s", docsDir, err)
	}

	product := parseProductConfig()
	command := "./run_with_libvirt.py"
	cmd := exec.Command(command, product.Short_name, product.Version)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Running '%s' failed with: %s", command, err)
	}
}

func doTestbedQemu() {
	docsDir := path.Join(repoRootPath, "testbed")
	err := os.Chdir(docsDir)
	if err != nil {
		Error.Fatalf("Could not chdir to '%s': %s", docsDir, err)
	}

	product := parseProductConfig()
	command := "./create_qemu_image.sh"
	cmd := exec.Command(command, product.Short_name, product.Version)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Running '%s' failed with: %s", command, err)
	}

	doTestbedRun()
}
