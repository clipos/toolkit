# Helper scripts for the CLIP OS project development common tasks

* Bash/ZSH function helper command for improved `repo forall -c <cmd>` output
  (warning: `cmd` can not include arguments with spaces):

```
rfa() {
    cmd="${@}"
    repo forall -j 1 -c "echo \$REPO_PROJECT; ${cmd}; echo ''"
}
```

  Warning: 'cmd' can not include arguments with spaces

* Bash/ZSH function helper command for pretty and selective `repo forall -c
  <cmd>` output (warning: `cmd` can not include arguments with spaces):

```
rfm() {
    cmd="${@}"
    repo forall -j 1 -c "${PWD}/toolkit/helpers/filter-most.sh ${cmd}"
}
```

* Update Git remotes with the upstream defined in the manifest:

```
declare-upstreams() {
    repo forall "${@}" -c "${PWD}/toolkit/helpers/declare-upstreams.sh"
}
```

* Fetch the Git references from upstream remotes defined with
  "declare-upstreams"

```
fetch-upstreams() {
    repo forall "${@}" -c "${PWD}/toolkit/helpers/fetch-upstreams.sh"
}
```

* Switch to master branch for all projects:

```
master() {:
    repo start master --all
}
```
