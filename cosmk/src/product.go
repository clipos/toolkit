package main

import (
	"fmt"
	"io/ioutil"
	"path"

	"github.com/BurntSushi/toml"
)

type product struct {
	Version     string
	Common_name string
	Short_name  string
	Homepage    string
	Recipes     []string
	Environment map[string]string
}

func parseProductConfig() *product {
	content, err := ioutil.ReadFile(path.Join(repoRootPath, "products", rootConfig.Product.Name, "product.toml"))
	if err != nil {
		Error.Fatalln("Could not read 'product.toml':", err)
	}

	var p product
	_, err = toml.Decode(string(content), &p)
	if err != nil {
		Error.Fatalln("Could not parse 'product.toml':", err)
	}

	return &p
}

func (p *product) do() error {
	for _, recipe := range p.Recipes {
		r := parseRecipeConfig(recipe)
		err := r.do()
		if err != nil {
			return err
		}
	}
	return nil
}

func (p *product) reconfigure() error {
	for _, recipe := range p.Recipes {
		r := parseRecipeConfig(recipe)
		for _, action := range r.Actions {
			if (action != "build") && (action != "image") {
				err := r.action(action)
				if err != nil {
					return err
				}
			}
		}
	}
	return nil
}

func (p *product) env() []string {
	var env []string

	env = append(env, "--env", fmt.Sprintf("COSMK_PRODUCT_VERSION=%s", p.Version))
	var taintedVersion string
	if len(rootConfig.Development.Instrumentation) == 0 {
		taintedVersion = p.Version
	} else {
		taintedVersion = fmt.Sprintf("%s+%s", p.Version, "instrumented")
	}
	env = append(env, "--env", fmt.Sprintf("COSMK_PRODUCT_TAINTED_VERSION=%s", taintedVersion))

	env = append(env, "--env", fmt.Sprintf("COSMK_PRODUCT_COMMON_NAME=%s", p.Common_name))
	env = append(env, "--env", fmt.Sprintf("COSMK_PRODUCT_SHORT_NAME=%s", p.Short_name))
	env = append(env, "--env", fmt.Sprintf("COSMK_PRODUCT=%s", p.Short_name))
	env = append(env, "--env", fmt.Sprintf("COSMK_PRODUCT_HOMEPAGE=%s", p.Homepage))

	for k, v := range p.Environment {
		env = append(env, "--env", fmt.Sprintf("COSMK_PRODUCT_ENV_%s=%s", k, v))
	}

	return env
}
