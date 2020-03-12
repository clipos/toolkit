package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path"
	"strings"
)

var repoRootPath string
var version string = ""

// Must use default 'log' logger here as the log setup happens later
func findRepoRootPath() string {
	currentPath, err := os.Getwd()
	if err != nil {
		log.Fatalf("Could not get current working directory: %s", err)
	}
	for {
		// log.Println("Looking at:", currentPath)
		if currentPath == "/" {
			log.Fatal("Could not find project repo root path")
		}
		fi, err := os.Lstat(path.Join(currentPath, ".repo"))
		if err == nil {
			if fi.IsDir() {
				// log.Println("Found repo root path at:", currentPath)
				return currentPath
			}
		}
		currentPath = path.Dir(currentPath)
	}
}

// TODO: Improve the version check logic
// Must use default 'log' logger here as the log setup happens later
func versionCheck(version string) {
	versionFile := path.Join(repoRootPath, "toolkit", "cosmk", "version")
	content, err := ioutil.ReadFile(versionFile)
	if err != nil {
		log.Fatalf("Could not open version file '%s': %s", versionFile, err)
	}

	versionFromFile := string(content)
	if versionFromFile != version {
		log.Fatalf("Current cosmk is '%s' while repository version is '%s'. Please rebuild cosmk.", version, versionFromFile)
	}
}

// Must use default 'log' logger here as the log setup happens later
func listGeneric(kind string) []string {
	productPath := path.Join(repoRootPath, "products", rootConfig.Product.Name)
	files, err := ioutil.ReadDir(productPath)
	if err != nil {
		log.Fatalf("Could not list directory '%s': %s", productPath, err)
	}

	var kinds []string
	for _, file := range files {
		// Ignore hidden files & directories
		if strings.HasPrefix(file.Name(), ".") {
			continue
		}
		if file.IsDir() {
			kindToml := path.Join(repoRootPath, "products", rootConfig.Product.Name, file.Name(), fmt.Sprintf("%s.toml", kind))
			_, err := os.Stat(kindToml)
			if err != nil {
				// log.Printf("Could not open file '%s': %s", kindToml, err)
				continue
			}
			kinds = append(kinds, file.Name())
		}
	}

	return kinds
}

func listSdks() []string {
	return listGeneric("sdk")
}

func listRecipes() []string {
	return listGeneric("recipe")
}

func listAll() []string {
	return append(listSdks(), listRecipes()...)
}

func doCache() {
	err := os.Chdir(repoRootPath)
	if err != nil {
		Error.Fatalf("Could not chdir to '%s': %s", repoRootPath, err)
	}

	cachePath := path.Join(repoRootPath, "cache")
	_, err = os.Stat(cachePath)
	if err == nil {
		Error.Fatalf("Remove the 'cache' folder before proceeding.")
	} else if !os.IsNotExist(err) {
		Error.Fatalf("Could not stat '%s': %s", cachePath, err)
	}

	// GitLab API URL to get the latest successful build
	url := fmt.Sprintf("%s/api/v4/projects/%s/pipelines?scope=finished&status=success", rootConfig.Ci.Url, rootConfig.Ci.Project_id)
	Debug.Printf("Requesting pipeline status from %s", url)
	resp, err := http.Get(url)
	if err != nil {
		Error.Fatalf("Could not get pipeline status: %s", err)
	}
	defer resp.Body.Close()

	body, err := ioutil.ReadAll(resp.Body)
	Debug.Printf("Received: %s", body)

	var pipeline []map[string]interface{}
	err = json.Unmarshal([]byte(body), &pipeline)
	if err != nil {
		Error.Fatalf("Could not parse received JSON from the GitLab API: %s", err)
	}

	Debug.Printf("Parsed json: %s", pipeline)

	buildID := 0.
	for _, build := range pipeline {
		buildID = build["id"].(float64)
		break
	}
	if buildID == 0. {
		Error.Fatalf("Could not find the latest successful pipeline.")
	}
	Debug.Printf("Retrieving binary packages from build ID: %d", int(buildID))

	// TODO: Import get-cache-from-ci.sh logic here
	command := path.Join(repoRootPath, "toolkit", "helpers", "get-cache-from-ci.sh")
	cmd := exec.Command(command, fmt.Sprintf("https://files.clip-os.org/%d", int(buildID)))
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Running '%s' failed with: %s", command, err)
	}
}

// Logging helpers
var (
	Debug *log.Logger
	Info  *log.Logger
	Error *log.Logger
)

func initLogging(debug *bool) {
	if *debug {
		Debug = log.New(os.Stdout, "DEBUG:   ", log.Ldate|log.Ltime|log.Lshortfile)
		Info = log.New(os.Stdout, "INFO:    ", log.Ldate|log.Ltime|log.Lshortfile)
		Error = log.New(os.Stderr, "ERROR:   ", log.Ldate|log.Ltime|log.Lshortfile)
		Debug.Println("Log level set to debug")
	} else {
		Debug = log.New(ioutil.Discard, "", 0)
		Info = log.New(os.Stdout, "[*] ", 0)
		Error = log.New(os.Stdout, "[!] ", 0)
	}
}
