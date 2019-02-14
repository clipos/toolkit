# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright © 2017 ANSSI. All rights reserved.

# Script to be sourced to setup the interactive shell environment of the user
# to allow him/her to use the whole CLIP OS toolkit easily (cosmk with the
# shell completion features, our vendored version of just, etc.).

# DISCLAIMER: For now, only Bash and Zsh shells are supported.

# Development guidelines for this file:
#   1. Do NOT call "exit" as this would close the user interactive shell
#      session. Use return!
#   2. Stay POSIX sh compliant for this file (with the exception of the "local"
#      keyword which is understood everywhere).
#   3. Avoid at most the use of external programs (aliases might have been
#      set in the current interactive shell session that could possibly break
#      the expected behavior of some commands).
#   4. Use double-underscore prefixed variable and function names to avoid
#      overwriting potential variables or functions of the user interactive
#      shell.

# Identify the running shell as code will differ if it is either Bash or Zsh:
if [ -n "$ZSH_VERSION" ]; then
   __shell_type=zsh
elif [ -n "$BASH_VERSION" ]; then
   __shell_type=bash
else
    echo >&2 " [!] Sorry, this script is meant to be sourced from either a Bash or a Zsh shell."
    echo >&2 "     No other shell is supported. Aborting."
    return 1 || exit 1  # if ever this script has been called
fi

# Get the path to myself (this current file) in order to compute my location
# and infer then the path to the toolkit directory.
case "$__shell_type" in
    bash)   __path_to_myself="${BASH_SOURCE[0]}" ;;
    zsh)    __path_to_myself="${(%):-%x}" ;;
esac
__path_to_toolkit="${__path_to_myself%/*}"
if [ "${__path_to_myself}" = "${__path_to_toolkit}" ]; then
    # if there is no slash in __path_to_myself then assume it is in the current
    # working directory:
    __path_to_toolkit="$(pwd)"
fi
# We can now infer the paths to the repo root and the toolkit runtime
# directory:
__path_to_repo_root="${__path_to_toolkit}/../"
__path_to_runtime_dir="${__path_to_repo_root}/run/"

__check_current_user_not_root() {
    if [ "$(id -u)" -eq 0 ]; then
        echo >&2 " [!] You should not be running this in a root interactive shell."
        echo >&2 "     Please retry with an unprivileged user."
        return 1
    fi
}

__check_not_already_in_venv() {
    if [ -n "${VIRTUAL_ENV}" ]; then
        echo >&2 " [!] You seem to already have a virtualenv activated."
        echo >&2 "     Please \"deactivate\" the current virtualenv to continue."
        return 1
    fi
}

__prepare_toolkit_runtime_dir() {
    mkdir -p "${__path_to_runtime_dir}"
}

__check_shell_umask() {
    if [ -n "${NO_UMASK_WARNING:-}" ]; then
        echo >&2 " [!] Current umask value check dismissed by request (NO_UMASK_WARNING variable set)."
        return 0
    fi

    local current_umask
    current_umask="$(umask)"
    case "${current_umask}" in
        # umask values known to cause no issues with cosmk
        0022|022|0002|002) ;;
        *)
            echo >&2 # line break
            cat >&2 <<END_OF_BANNER
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @                                                                         @
  @            Warning! You seem to use an unusual umask value.             @
  @                                                                         @
  @ This may lead to undefined problems when using the CLIP OS toolkit as   @
  @ all the file modes of this source tree are left unchanged when they are @
  @ exposed within SDK containers. As a consequence, some unprivileged      @
  @ programs running in these containers might encounter a "Permission      @
  @ denied" error when trying to read files from this source tree as their  @
  @ file access mode deny read/traversal for other users.                   @
  @                                                                         @
  @ Please make sure to have fetched and synchonized your source tree with  @
  @ repo with a umask value granting read and directory traversal for       @
  @ others (e.g., "umask 0022").                                            @
  @                                                                         @
  @ If you think this is not justified or you perfectly know what you are   @
  @ doing, you can proceed by setting NO_UMASK_WARNING=1 in your            @
  @ environment to circumvent this check and then reinvoke the source       @
  @ command.                                                                @
  @ Otherwise, please read carefully the section relative the developer     @
  @ environment setup in the CLIP OS toolkit documentation before           @
  @ proceeding. Thank you.                                                  @
  @                                                                         @
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
END_OF_BANNER
            echo >&2 # line break
            return 1
            ;;
    esac
}

__check_lfs_repositories() {
    # Do not process this check if told so:
    if [ -n "${NO_GIT_LFS_WARNING:-}" ]; then
        echo >&2 " [!] Git LFS repositories check dismissed by request (NO_GIT_LFS_WARNING variable set)."
        return 0
    fi

    # Abort this check if git is not present in PATH (this source tree may have
    # been retrieved from an archive file):
    if ! type git >/dev/null 2>&1; then
        echo >&2 " [!] Git is missing in the current environment: Git LFS repositories check dismissed."
        return 0
    fi

    # Likewise, abort this check if the source tree root is not backed by repo
    # (the source tree may also have been reconstructed from an archive file):
    if ! [ -d "${__path_to_repo_root}/.repo" ]; then
        echo >&2 " [!] This source tree does not seem to be managed by repo: Git LFS repositories check dismissed."
        return 0
    fi

    # Git is present and the source tree is backed by repo. We can therefore
    # check for the good condition of the Git LFS-backed repositories:
    if ! "${__path_to_toolkit}/helpers/check-lfs-repositories.sh" --quick; then
        echo >&2 # line break
        cat >&2 <<END_OF_BANNER
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @                                                                         @
  @      Warning! Some Git LFS-backed repositories seem to be missing       @
  @     Git LFS objects (either downloaded or checked out in the tree).     @
  @                                                                         @
  @ You may have synchronized the CLIP OS source tree without having        @
  @ activated prior the Git LFS filters globally with the command "git lfs  @
  @ install". As a consequence, you may have synchronized partially the     @
  @ source tree as the files stored with Git LFS are still missing in the   @
  @ concerned repositories.                                                 @
  @                                                                         @
  @ Please make sure you have fetched and synchonized your source tree in a @
  @ Git LFS initialized environment. If this was not the case and if the    @
  @ advertised Git LFS endpoint is reachable, you can simply run the        @
  @ following command to finish the download of the missing Git LFS objects @
  @ and checked them out properly in the source tree:                       @
  @                                                                         @
  @   $ repo forall -g lfs -c 'git lfs install && git lfs pull'             @
  @                                                                         @
  @ If you think this is not justified or if you perfectly know what you    @
  @ are doing, you can proceed by setting NO_GIT_LFS_WARNING=1 in your      @
  @ environment to circumvent this check and then reinvoke the source       @
  @ command.                                                                @
  @ Otherwise, please read carefully the section relative the developer     @
  @ environment setup in the CLIP OS toolkit documentation before           @
  @ proceeding. Thank you.                                                  @
  @                                                                         @
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
END_OF_BANNER
        echo >&2 # line break
        return 1
    else
        echo >&2 " [*] Git LFS-backed repositories seem to be properly checked out."
    fi
}

__setup_and_activate_venv() {
    echo >&2 " [*] Setting up a dedicated virtualenv for the CLIP OS toolkit..."
    echo >&2 "     Please be patient as this may take some time on the first run."
    "${__path_to_toolkit}/setup_venv.sh" >| "${__path_to_runtime_dir}/virtualenv_setup.log" 2>&1
    if [ "$?" -eq 0 ]; then
        . "${__path_to_runtime_dir}/venv/bin/activate" >| "${__path_to_runtime_dir}/virtualenv_activation.log" 2>&1
        if [ "$?" -eq 0 ]; then
            echo >&2 " [*] CLIP OS toolkit virtualenv successfully activated for the current shell."
        else
            cat >&2 "${__path_to_runtime_dir}/virtualenv_activation.log"
            echo >&2 # line break
            echo >&2 " [!] Unknown error: virtualenv activation has failed."
            echo >&2 "     The log output above is stored in \"run/virtualenv_activation.log\" (from the source tree root level)."
            return 1
        fi
    else
        cat >&2 "${__path_to_runtime_dir}/virtualenv_setup.log"
        echo >&2 # line break
        echo >&2 " [!] Virtualenv setup has failed."
        echo >&2 "     The log output above is stored in \"run/virtualenv_setup.log\" (from the source tree root level)."
        return 1
    fi
}

__cosmk_bash_completion() {
    echo >&2 " [*] Registering shell completion helpers for \"cosmk\" commands..."
    if type register-python-argcomplete cosmk >/dev/null 2>&1; then
        if [ "${__shell_type}" = "zsh" ]; then
            if ! type compinit >/dev/null 2>&1; then
                echo >&2 " [!] Zsh-specific: shell completion feature (compinit) is not loaded."
                echo >&2 "     \"cosmk\" shell completion won't work."
                return 0
            elif ! type complete >/dev/null 2>&1; then
                echo >&2 " [*] Zsh-specific: Bash-compatible completion feature (bashcompinit) is not loaded."
                echo >&2 "     Autoloading Bash-compatible completion feature..."
                autoload -Uz bashcompinit
                bashcompinit
                if [ "$?" -ne 0 ]; then
                    echo >&2 " [!] Zsh-specific: Could not load bashcompinit."
                    echo >&2 "     \"cosmk\" shell completion won't work."
                    return 0
                fi
            fi
        elif [ "${__shell_type}" = "bash" ]; then
            if ! type complete >/dev/null 2>&1; then
                echo >&2 " [!] Bash-specific: shell completion feature (complete) is not present."
                echo >&2 "     \"cosmk\" shell completion won't work."
                return 0
            fi
        fi

        # Load the bash completion for cosmk:
        eval "$(register-python-argcomplete -s bash --no-defaults cosmk)"
    else
        echo >&2 " [!] Unknown error: could not register shell completion helpers."
        return 1
    fi
}

__sujust_alias() {
    echo >&2 " [*] Declaring special alias \"sujust\" to be able to call \"just\" with super-user privileges."
    echo >&2 "     This alias circumvents the environment sanitizing feature of \"sudo\" which cause issues in our setup."

    # Note/Hack: we need to get through the `env` binary (which semantically
    # does nothing here) in order to circumvent the binary path resolution
    # (i.e.  iterating over PATH to find the requested binary) done by sudo
    # which seem to resolve the requested binary with the "secure_path"
    # variable value (see sudo configuration) even though we tell sudo to
    # preserve the environment variable PATH
    # This hack is there to permit the user to call the `just` program (which
    # reside in an unsual path) with `sudo` easily.
    alias sujust='sudo -E --preserve-env=PATH env just'
}

__symlink_repo_root_justfile() {
    echo >&2 " [*] Symlinking the justfile dedicated to the source tree root into its expected location."
    ln -snf "toolkit/repo_root.justfile" "${__path_to_repo_root}/justfile"
}

# Chain the functions and grab the first non-null return code "raised"
__source_me_return_code__=0
__check_current_user_not_root \
    && __check_not_already_in_venv \
    && __prepare_toolkit_runtime_dir \
    && __check_shell_umask \
    && __check_lfs_repositories \
    && __setup_and_activate_venv \
    && __cosmk_bash_completion \
    && __sujust_alias \
    && __symlink_repo_root_justfile \
        || __source_me_return_code__="$?"

# Avoid polluting the user's shell environment with our internal stuff:
unset -v __shell_type \
    __path_to_myself \
    __path_to_toolkit \
    __path_to_repo_root \
    __path_to_runtime_dir
unset -f __check_current_user_not_root \
    __check_not_already_in_venv \
    __prepare_toolkit_runtime_dir \
    __check_shell_umask \
    __check_lfs_repositories \
    __setup_and_activate_venv \
    __cosmk_bash_completion \
    __sujust_alias \
    __symlink_repo_root_justfile

# propagate the return code
return "${__source_me_return_code__}"
