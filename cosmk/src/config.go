package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path"

	"github.com/BurntSushi/toml"
)

var rootConfig config

type config struct {
	Product     configProduct
	Ci          configCi
	Development configDevelopment
}

type configProduct struct {
	Name string
}

type configCi struct {
	Url        string
	Registry   string
	Project_id string
	Artifacts  string
}

type configDevelopment struct {
	Network         string
	Instrumentation []string
}

// Must use default 'log' logger here as the log setup happens later
func parseConfig() {
	content, err := ioutil.ReadFile(path.Join(repoRootPath, "config.toml"))
	if err != nil {
		log.Fatalln("Could not read 'config.toml':", err)
	}

	_, err = toml.Decode(string(content), &rootConfig)
	if err != nil {
		log.Fatalln("Could not parse 'config.toml':", err)
	}

	if rootConfig.Product.Name == "" {
		log.Fatalln("Please select a product to build in 'config.toml'.")
	}
}

// List enabled instrumentation features or test if selected feature is enabled
func doInstrumentationFeatures() {
	// Has a specific feature been selected?
	if *instrumentationFeature != "" {
		// Test if selected feature is enabled
		for _, feat := range rootConfig.Development.Instrumentation {
			if *instrumentationFeature == feat {
				println("true")
				os.Exit(0)
			}
		}
		println("false")
		os.Exit(1)
	} else {
		// List enabled instrumentation features
		for _, feat := range rootConfig.Development.Instrumentation {
			println(feat)
		}
	}
}

func (c *config) env() []string {
	features := ""

	for _, v := range c.Development.Instrumentation {
		if features == "" {
			features += v
		} else {
			features += " " + v
		}
	}

	return []string{
		"--env",
		fmt.Sprintf("COSMK_INSTRUMENTATION_FEATURES=%s", features),
	}
}
