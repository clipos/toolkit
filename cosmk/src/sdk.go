package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"path"
	"strings"

	"github.com/BurntSushi/toml"
)

type sdkToml struct {
	Tag         string
	Bootstrap   sdkBootstrap
	Build       sdkBuild
	Environment map[string]string
}

type sdkBootstrap struct {
	Rootfs string
	Steps  []string
}

type sdkBuild struct {
	Capabilities    []string
	Writable_assets []string
}

type sdk struct {
	Name        string
	Tag         string
	Bootstrap   sdkBootstrap
	Build       sdkBuild
	Environment map[string]string
	Product     *product
}

func parseSdkConfig(name string) sdk {
	product := parseProductConfig()

	name = strings.TrimPrefix(name, fmt.Sprintf("%s/", product.Short_name))

	content, err := ioutil.ReadFile(path.Join(repoRootPath, "products", rootConfig.Product.Name, name, "sdk.toml"))
	if err != nil {
		Error.Fatalln("Could not read 'sdk.toml':", err)
	}

	var s sdkToml
	_, err = toml.Decode(string(content), &s)
	if err != nil {
		Error.Fatalln("Could not parse 'sdk.toml':", err)
	}

	return sdk{
		Name:        name,
		Tag:         s.Tag,
		Bootstrap:   s.Bootstrap,
		Build:       s.Build,
		Environment: s.Environment,
		Product:     product,
	}
}

func (s *sdk) env() []string {
	var env []string

	env = append(env, "--env", fmt.Sprintf("COSMK_SDK_PRODUCT=%s", s.Product.Short_name))
	env = append(env, "--env", fmt.Sprintf("COSMK_SDK_RECIPE=%s", s.Name))

	for k, v := range s.Environment {
		env = append(env, "--env", fmt.Sprintf("COSMK_SDK_ENV_%s=%s", k, v))
	}
	return env
}

func (s *sdk) bootstrap() error {
	imageName := fmt.Sprintf("%s/%s", rootConfig.Product.Name, s.Name)
	Debug.Printf("Bootstrapping '%s:%s'", imageName, s.Tag)

	if rootConfig.Ci.Registry != "" {
		err := runtime.findCiImage(imageName, s.Tag)
		if err == nil {
			Debug.Printf("No need to bootstrap '%s:%s'", imageName, s.Tag)
			return nil
		}
	}

	err := runtime.findLocalImage(imageName, s.Tag)
	if err == nil {
		Debug.Printf("No need to bootstrap '%s:%s'", imageName, s.Tag)
		return nil
	}

	Info.Printf("No image found. Bootstrapping image '%s:%s' from scratch", imageName, s.Tag)

	bootstrapVersion := fmt.Sprintf("%s.bootstrap", s.Tag)
	err = runtime.findLocalImage(imageName, bootstrapVersion)
	if err != nil {
		rootfs := path.Join(repoRootPath, s.Bootstrap.Rootfs)
		Info.Printf("Importing rootfs from '%s'", s.Bootstrap.Rootfs)
		cmd := runtime.command()
		cmd.Args = append(cmd.Args, "import", rootfs, fmt.Sprintf("localhost/%s:%s", imageName, bootstrapVersion))
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		err = cmd.Run()
		if err != nil {
			Error.Fatalf("Could not import rootfs from '%s': %s", rootfs, err)
		}
	}

	workContainer := fmt.Sprintf("%s_%s.%s.working", s.Product.Short_name, s.Name, "bootstrap")
	Debug.Printf("Removing temporary container '%s'", workContainer)
	cmd := runtime.command()
	cmd.Args = append(cmd.Args, "rm", workContainer)
	err = cmd.Run()
	if err != nil {
		Debug.Printf("Could not remove temporary container '%s': %s", workContainer, err)
	}
	Debug.Printf("Removed temporary container '%s'", workContainer)

	Info.Printf("Running bootstrap step for '%s'", fmt.Sprintf("%s:%s", imageName, bootstrapVersion))
	err = runtime.run(fmt.Sprintf("localhost/%s:%s", imageName, bootstrapVersion), []string{"./bootstrap.sh"}, "bootstrap", s, nil)
	if err != nil {
		return err
	}

	Info.Printf("Commiting final image '%s:%s'", imageName, s.Tag)
	cmd = runtime.command()
	cmd.Args = append(cmd.Args, "commit", workContainer, fmt.Sprintf("%s:%s", imageName, s.Tag))
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Could not commit final SDK image: %s", err)
	}
	Info.Printf("Sucessfully commited final image '%s:%s '", imageName, s.Tag)

	Info.Printf("Removing temporary container '%s'", workContainer)
	cmd = runtime.command()
	cmd.Args = append(cmd.Args, "rm", workContainer)
	err = cmd.Run()
	if err != nil {
		Error.Fatalf("Could not remove temporary container '%s': %s", workContainer, err)
	}
	Info.Printf("Removed temporary container '%s'", workContainer)

	return nil
}

func (s *sdk) run(command []string) error {
	err := s.bootstrap()
	if err != nil {
		return err
	}
	imageName := fmt.Sprintf("%s/%s", rootConfig.Product.Name, s.Name)
	return runtime.run(fmt.Sprintf("%s:%s", imageName, s.Tag), command, "run", s, nil)
}
