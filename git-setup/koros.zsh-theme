# vim:ft=zsh ts=2 sw=2 sts=2

function prompt_char {
	if [ $UID -eq 0 ]; then echo "#"; else echo %%; fi
}

function prompt_virtualenv {
	[[ -n "$VIRTUAL_ENV" && -n $VIRTUAL_ENV_DISABLE_PROMPT ]] && echo -n "%{$fg_bold[green]%}(${VIRTUAL_ENV:t})%{$reset_color%} " || echo -n ""
}

local ret_status="%(?:%{$fg_bold[yellow]%}@:%{$fg_bold[red]%}@)"

PROMPT='[$(prompt_virtualenv)%(!.%{$fg_bold[red]%}.%{$fg_bold[blue]%}%n${ret_status})%{$fg_bold[white]%}%m%{$reset_color%}][%{$fg[magenta]%}%1~%{$reset_color%}] %{$fg_bold[yellow]%}$(git_prompt_info)% %{$fg[blue]%}$(prompt_char)%{$reset_color%} '

ZSH_THEME_GIT_PROMPT_PREFIX="\ue0a0 "
ZSH_THEME_GIT_PROMPT_SUFFIX=" "
