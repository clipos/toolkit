package main

import (
	"fmt"
	"log"
	"os"

	"gopkg.in/alecthomas/kingpin.v2"
)

var (
	debug = kingpin.Flag("debug", "Enable debug output.").Short('d').Bool()

	repoRootPathCmd = kingpin.Command("repo-root-path", "Output on stdout the repo root absolute path.")

	productNameCmd    = kingpin.Command("product-name", "Output on stdout the product name set in config.toml.")
	productVersionCmd = kingpin.Command("product-version", "Output on stdout the product version set in config.toml.")
	ciRegistryCmd     = kingpin.Command("ci-registry", "Output on stdout the registry configured in the CI section in config.toml.")

	instrumentationFeaturesCmd = kingpin.Command("instrumentation-features", "List of enabled instrumentation features set in config.toml.")
	instrumentationFeature     = instrumentationFeaturesCmd.Arg("feature", "Test if given instrumentation feature is enabled.").String()

	cacheCmd = kingpin.Command("cache", "Download pre-built binary packages from the CI.")

	docCmd      = kingpin.Command("doc", "")
	docBuildCmd = docCmd.Command("build", "Build the documentation.")
	docOpenCmd  = docCmd.Command("open", "Open the documentation in the default browser, building it if necessary.")
	docCleanCmd = docCmd.Command("clean", "Remove documentation build folder.")

	allCmd = kingpin.Command("all", "Run all steps required to build a product.")

	reconfCmd = kingpin.Command("reconf", "Build a product but skip 'build' & 'image' steps (iterative rebuild/reconfiguration).")

	bootstrapCmd = kingpin.Command("bootstrap", "Bootstrap a SDK recipe.")
	bootstrapSdk = bootstrapCmd.Arg("recipe", "recipe to use.").HintAction(listSdks).Required().String()

	containerCmd = kingpin.Command("container", "Output on stdout the container name and tag for the given Sdk recipe.")
	containerSdk = containerCmd.Arg("recipe", "Sdk to use.").HintAction(listSdks).Required().String()

	runCmd     = kingpin.Command("run", "Start a shell in the SDK set for a recipe.")
	runRecipe  = runCmd.Arg("recipe", "SDK or recipe to use.").HintAction(listAll).Required().String()
	runCmdArgs = runCmd.Arg("command", "Command with arguments to run inside the SDK.").Strings()

	buildCmd    = kingpin.Command("build", "Build from source the rootfs of a given recipe.")
	buildRecipe = buildCmd.Arg("recipe", "recipe to use.").HintAction(listRecipes).Required().String()

	imageCmd    = kingpin.Command("image", "Build the rootfs of a given recipe from the cache produced during the \"build\" action step.")
	imageRecipe = imageCmd.Arg("recipe", "recipe to use").HintAction(listRecipes).Required().String()

	configureCmd    = kingpin.Command("configure", "Apply configuration scripts for a given recipe.")
	configureRecipe = configureCmd.Arg("recipe", "recipe to use.").HintAction(listRecipes).Required().String()

	bundleCmd    = kingpin.Command("bundle", "Bundle a recipe.")
	bundleRecipe = bundleCmd.Arg("recipe", "recipe to use.").HintAction(listRecipes).Required().String()

	testCmd      = kingpin.Command("test", "")
	testSetupCmd = testCmd.Command("setup", "Setup the testbed environment (build the vagrant boxes and call 'vagrant up'.")
	testQemuCmd  = testCmd.Command("qemu", "Create a QEMU image for testing and start a VM in the virtual testbed.")
	testRunCmd   = testCmd.Command("run", "Start a VM in the virtual testbed.")
)

func main() {
	// Find the project root directory
	repoRootPath = findRepoRootPath()

	// Initial version check to make sure that we are running the version currently available in the repository
	if version == "" {
		log.Fatal("cosmk was not build with version information. Please see the README.")
	}
	versionCheck(version)

	// Parse config.toml to find the selected product
	parseConfig()

	// Setup and parse command line
	kingpin.Version(version)
	kingpin.CommandLine.HelpFlag.Short('h')
	kingpin.CommandLine.VersionFlag.Short('v')
	command := kingpin.Parse()

	// Setup logging now that we know if we are running in debug mode or not
	initLogging(debug)

	switch command {
	case "repo-root-path":
		fmt.Fprintf(os.Stdout, repoRootPath)

	case "product-name":
		fmt.Fprintf(os.Stdout, parseProductConfig().Short_name)

	case "product-version":
		fmt.Fprintf(os.Stdout, parseProductConfig().Version)

	case "ci-registry":
		fmt.Fprintf(os.Stdout, rootConfig.Ci.Registry)

	case "instrumentation-features":
		doInstrumentationFeatures()

	case "cache":
		doCache()

	case docBuildCmd.FullCommand():
		doBuildDoc()
	case docOpenCmd.FullCommand():
		doOpenDoc()
	case docCleanCmd.FullCommand():
		doCleanDoc()

	case "all":
		findContainerRuntime()
		err := parseProductConfig().do()
		if err != nil {
			Error.Fatalf("Error: %s", err)
		}

	case "reconf":
		findContainerRuntime()
		err := parseProductConfig().reconfigure()
		if err != nil {
			Error.Fatalf("Error: %s", err)
		}

	case "bootstrap":
		findContainerRuntime()
		s := parseSdkConfig(*bootstrapSdk)
		err := s.bootstrap()
		if err != nil {
			Error.Fatalf("Error: %s", err)
		}

	case "container":
		findContainerRuntime()
		s := parseSdkConfig(*containerSdk)
		fmt.Fprintf(os.Stdout, "%s/%s:%s", rootConfig.Product.Name, s.Name, s.Tag)

	case "run":
		findContainerRuntime()
		command := []string{"bash"}
		if runCmdArgs != nil && len(*runCmdArgs) > 0 {
			command = *runCmdArgs
		}
		for _, r := range listSdks() {
			if r == *runRecipe {
				sdk := parseSdkConfig(*runRecipe)
				sdk.run(command)
				return
			}
		}
		r := parseRecipeConfig(*runRecipe)
		r.run(command)

	case "build":
		findContainerRuntime()
		recipe := parseRecipeConfig(*buildRecipe)
		recipe.action("build")

	case "image":
		findContainerRuntime()
		recipe := parseRecipeConfig(*imageRecipe)
		recipe.action("image")

	case "configure":
		findContainerRuntime()
		recipe := parseRecipeConfig(*configureRecipe)
		recipe.action("configure")

	case "bundle":
		findContainerRuntime()
		recipe := parseRecipeConfig(*bundleRecipe)
		recipe.action("bundle")

	case testSetupCmd.FullCommand():
		doTestbedSetup()
	case testQemuCmd.FullCommand():
		doTestbedQemu()
	case testRunCmd.FullCommand():
		doTestbedRun()
	}
}
