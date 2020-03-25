# CLIP OS project & build toolkit

The full documentation for the CLIP OS project and this toolkit is available at
<https://docs.clip-os.org>.

## Build

```
$ go build -o cosmk -mod=vendor -ldflags "-X main.version=$(cat version | tr -d '\n')" ./src
```

## Interactive shell completion

Add `cosmk` to you PATH and the following to your shell startup script:

```
# Bash
eval "$(cosmk --completion-script-bash)"

# Zsh
eval "$(cosmk --completion-script-zsh)"
```

## Development

Vendor Go modules with:

```
$ go mod vendor
```
