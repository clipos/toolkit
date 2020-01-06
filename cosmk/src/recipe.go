package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"path"

	"github.com/BurntSushi/toml"
)

type recipeToml struct {
	Sdk         string
	Actions     []string
	Environment map[string]string
}

type recipe struct {
	Name        string
	Actions     []string
	Environment map[string]string
	Sdk         *sdk
	Product     *product
}

func parseRecipeConfig(name string) recipe {
	product := parseProductConfig()

	content, err := ioutil.ReadFile(path.Join(repoRootPath, "products", rootConfig.Product.Name, name, "recipe.toml"))
	if err != nil {
		Error.Fatalln("Could not read 'recipe.toml':", err)
	}

	var r recipeToml
	_, err = toml.Decode(string(content), &r)
	if err != nil {
		Error.Fatalln("Could not parse 'recipe.toml':", err)
	}

	s := parseSdkConfig(r.Sdk)

	return recipe{
		Name:        name,
		Actions:     r.Actions,
		Environment: r.Environment,
		Sdk:         &s,
		Product:     product,
	}
}

func (r *recipe) do() error {
	err := r.Sdk.bootstrap()
	if err != nil {
		return err
	}
	for _, action := range r.Actions {
		err = r.action(action)
		if err != nil {
			return err
		}
	}
	return nil
}

func (r *recipe) action(action string) error {
	err := r.Sdk.bootstrap()
	if err != nil {
		return err
	}

	// Search for the action script in the recipe directory first and if not
	// found, use the default one from the SDK
	hostCommand := path.Join(repoRootPath, "products", r.Product.Short_name,
		r.Name, fmt.Sprintf("%s.sh", action))
	sdkCommand := path.Join("/mnt", "products", r.Product.Short_name, r.Name, fmt.Sprintf("%s.sh", action))
	_, err = os.Stat(hostCommand)
	if err != nil {
		if !os.IsNotExist(err) {
			Error.Fatalf("Could not access file '%s': %s", hostCommand, err)
		}
		sdkCommand = fmt.Sprintf("./%s.sh", action)
	}

	imageName := fmt.Sprintf("%s/%s", rootConfig.Product.Name, r.Sdk.Name)
	return runtime.run(fmt.Sprintf("%s:%s", imageName, r.Sdk.Tag), []string{sdkCommand}, action, r.Sdk, r)
}

func (r *recipe) env() []string {
	var env []string

	for k, v := range r.Environment {
		env = append(env, "--env", fmt.Sprintf("COSMK_RECIPE_ENV_%s=%s", k, v))
	}

	return env
}

func (r *recipe) run(command []string) error {
	err := r.Sdk.bootstrap()
	if err != nil {
		return err
	}
	imageName := fmt.Sprintf("%s/%s", rootConfig.Product.Name, r.Sdk.Name)
	return runtime.run(fmt.Sprintf("%s:%s", imageName, r.Sdk.Tag), command, "run", r.Sdk, r)
}
