package main

import (
	"os"
	"os/exec"
	"path"
)

// Change current directory to "docs-src" and build the documentation
func doBuildDoc() {
	docsDir := path.Join(repoRootPath, "docs-src")
	err := os.Chdir(docsDir)
	if err != nil {
		Error.Fatalf("Could not chdir to '%s': %s", docsDir, err)
	}

	command := "./build.sh"
	cmd := exec.Command(command)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Running '%s' failed with: %s", command, err)
	}
}

// Build (if nothing as been build yet) and open the documentation in the default browser
func doOpenDoc() {
	indexPath := path.Join(repoRootPath, "docs-src", "_build", "index.html")
	_, err := os.Stat(indexPath)
	if err != nil {
		doBuildDoc()
	}

	command := "xdg-open"
	cmd := exec.Command(command, indexPath)
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Running '%s' failed with: %s", command, err)
	}
}

// Remove documentation build folder
func doCleanDoc() {
	buildPath := path.Join(repoRootPath, "docs-src", "_build")
	Info.Printf("Removing '%s'...", buildPath)
	err := os.RemoveAll(buildPath)
	if err != nil {
		Error.Fatalf("Error while removing '%s': %s", buildPath, err)
	}
}
