# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH
export PISTOL_CHROMA_FORMATTER=terminal16m
# Path to your Oh My Zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time Oh My Zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
ZSH_THEME="koros"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in $ZSH/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment one of the following lines to change the auto-update behavior
# zstyle ':omz:update' mode disabled  # disable automatic updates
# zstyle ':omz:update' mode auto      # update automatically without asking
# zstyle ':omz:update' mode reminder  # just remind me to update when it's time

# Uncomment the following line to change how often to auto-update (in days).
zstyle ':omz:update' frequency 13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS="true"

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# You can also set it to another string to have that shown instead of the default red dots.
# e.g. COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# Caution: this setting can cause issues with multiline prompts in zsh < 5.7.1 (see #5765)
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(zsh-autosuggestions zsh-syntax-highlighting)

source $ZSH/oh-my-zsh.sh
source ~/.scripts.sh
# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='nvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch $(uname -m)"

# Set personal aliases, overriding those provided by Oh My Zsh libs,
# plugins, and themes. Aliases can be placed here, though Oh My Zsh
# users are encouraged to define aliases within a top-level file in
# the $ZSH_CUSTOM folder, with .zsh extension. Examples:
# - $ZSH_CUSTOM/aliases.zsh
# - $ZSH_CUSTOM/macos.zsh
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"
 
# Sets Neovim as standard man pages reader
#export MANPAGER="nvim +Man!"

# vi mode
bindkey -v
export KEYTIMEOUT=1

# Change cursor shape for different vi modes.
function zle-keymap-select {
  if [[ ${KEYMAP} == vicmd ]] ||
     [[ $1 = 'block' ]]; then
    echo -ne '\e[2 q'
  elif [[ ${KEYMAP} == main ]] ||
       [[ ${KEYMAP} == viins ]] ||
       [[ ${KEYMAP} = '' ]] ||
       [[ $1 = 'beam' ]]; then
    echo -ne '\e[6 q'
  fi
}
zle -N zle-keymap-select
zle-line-init() {
    zle -K viins # initiate `vi insert` as keymap (can be removed if `bindkey -V` has been set elsewhere)
    echo -ne "\e[6 q"
}
zle -N zle-line-init
echo -ne '\e[6 q' # Use beam shape cursor on startup.
preexec() { echo -ne '\e[6 q' ;} # Use beam shape cursor for each new prompt.

### Aliases ###

alias cp="cp -v"
alias mv="mv -iv"
alias pm="pulsemixer"
alias bt="bluetoothctl"
alias yt="yt-dlp"
alias yta="yt-dlp -x -f bestaudio/best"
alias ytv="yt-dlp -f 'bv*+ba/best'"
alias fetch="fastfetch"
## MAC addresses
export airpods="5C:1B:F4:07:2D:BD"
export casse="7C:96:D2:56:99:32"
export jbl="88:92:CC:77:27:1E"

## Default editor
export EDITOR=nvim
export VISUAL=nvim


export PATH="$HOME/.local/bin:$PATH"

# ============================================================
# Proton Drive pseudo-shell
# ============================================================

typeset -g PD_CWD="/my-files"

# ------------------------------------------------------------
# Risolve un percorso remoto relativo a PD_CWD
# ------------------------------------------------------------

_pd_resolve() {
    local target="${1:-.}"
    local resolved

    if [[ "$target" == /* ]]; then
        resolved="$(realpath -m -- "$target")"
    else
        resolved="$(realpath -m -- "$PD_CWD/$target")"
    fi

    case "$resolved" in
        /my-files|/my-files/*)
            REPLY="$resolved"
            ;;
        *)
            print -u2 "Errore: percorso fuori da /my-files"
            return 1
            ;;
    esac
}

# ------------------------------------------------------------
# Mostra directory remota corrente
# ------------------------------------------------------------

pdpwd() {
    print -r -- "$PD_CWD"
}

# ------------------------------------------------------------
# Cambia directory remota
# ------------------------------------------------------------

pdc() {
    if (( $# == 0 )); then
        pdpwd
        return
    fi

    _pd_resolve "$1" || return
    PD_CWD="$REPLY"

    print -r -- "$PD_CWD"
}

# ------------------------------------------------------------
# Lista directory corrente
# ------------------------------------------------------------

pdl() {
    local target="${1:-.}"

    _pd_resolve "$target" || return
    proton-drive filesystem list "$REPLY"
}

# ------------------------------------------------------------
# Download
# ------------------------------------------------------------

pdget() {
    if (( $# == 0 )); then
        print -u2 "Uso: pdget FILE [DESTINAZIONE]"
        return 1
    fi

    _pd_resolve "$1" || return
    proton-drive filesystem download "$REPLY" "${2:-.}"
}

# ------------------------------------------------------------
# Upload
# ------------------------------------------------------------

pdput() {
    if (( $# == 0 )); then
        print -u2 "Uso: pdput FILE_LOCALE [CARTELLA_REMOTA]"
        return 1
    fi

    local destination="${2:-.}"

    _pd_resolve "$destination" || return
    proton-drive filesystem upload "$1" "$REPLY"
}

# ============================================================
# Autocompletamento Proton Drive
# ============================================================

_pd_complete_remote() {
    local current="$1"
    local mode="$2"

    local parent
    local prefix
    local display_prefix=""
    local remote_dir

    # ----------------------------------------
    # Percorso assoluto
    # ----------------------------------------

    if [[ "$current" == /* ]]; then

        parent="${current%/*}"
        prefix="${current##*/}"

        [[ -z "$parent" ]] && parent="/"

        remote_dir="$parent"

        display_prefix="${parent}/"

    # ----------------------------------------
    # Percorso relativo con sottocartella
    # ----------------------------------------

    elif [[ "$current" == */* ]]; then

        parent="${current%/*}"
        prefix="${current##*/}"

        _pd_resolve "$parent" || return

        remote_dir="$REPLY"

        display_prefix="${parent}/"

    # ----------------------------------------
    # Nome semplice
    # ----------------------------------------

    else

        parent="."
        prefix="$current"

        remote_dir="$PD_CWD"

        display_prefix=""

    fi

    # ----------------------------------------
    # Interroga Proton Drive
    # ----------------------------------------

    local json

    json="$(proton-drive filesystem list -j "$remote_dir" 2>/dev/null)" ||
        return

    # ----------------------------------------
    # Estrae nome e tipo dal JSON
    # ----------------------------------------

    local -a candidates
    candidates=()

    while IFS=$'\t' read -r name type; do

        [[ -z "$name" ]] && continue

        # Filtra ciò che è già stato digitato
        [[ "$name" == "$prefix"* ]] || continue

        # pdc: solo directory
        if [[ "$mode" == "dirs" && "$type" != "folder" ]]; then
            continue
        fi

        # Aggiunge / alle directory
        local candidate="$name"

        if [[ "$type" == "folder" ]]; then
            candidate="${candidate}/"
        fi

        candidate="${display_prefix}${candidate}"

        candidates+=("$candidate")

    done < <(
        printf '%s\n' "$json" |
            jq -r '
                ..
                | objects
                | select(
                    (.type? == "file" or .type? == "folder")
                    and (.name? != null)
                )
                | [
                    (.name.value // .name),
                    .type
                  ]
                | @tsv
            ' 2>/dev/null
    )

    (( ${#candidates[@]} )) || return

    compadd -- "${candidates[@]}"
}

# ------------------------------------------------------------
# pdc → solo directory
# ------------------------------------------------------------

_pd_complete_pdc() {
    _pd_complete_remote "$words[CURRENT]" "dirs"
}

# ------------------------------------------------------------
# pdl → file + directory
# ------------------------------------------------------------

_pd_complete_pdl() {
    _pd_complete_remote "$words[CURRENT]" "both"
}

# ------------------------------------------------------------
# pdget → file + directory
# ------------------------------------------------------------

_pd_complete_pdget() {
    # Primo argomento = percorso remoto
    if (( CURRENT == 2 )); then
        _pd_complete_remote "$words[CURRENT]" "both"
    fi
}

# ------------------------------------------------------------
# pdput → secondo argomento = destinazione remota
# ------------------------------------------------------------

_pd_complete_pdput() {
    if (( CURRENT == 3 )); then
        _pd_complete_remote "$words[CURRENT]" "dirs"
    fi
}

# ============================================================
# Attiva completion
# ============================================================

autoload -Uz compinit
compinit

compdef _pd_complete_pdc pdc
compdef _pd_complete_pdl pdl
compdef _pd_complete_pdget pdget
compdef _pd_complete_pdput pdput
