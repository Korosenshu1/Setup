#!/bin/bash

keymap_file="$HOME/.cache/loaded_kmap"
source "$keymap_file"
if [[ "$kmap" == "us" ]]; then 
	setxkbmap it
	setxkbmap -option caps:swapescape,compose:ralt
	kmap=it
	notify-send -u low "Layout italiano caricato!" 
else
	setxkbmap us
	setxkbmap -option caps:swapescape,compose:ralt
	kmap=us
	notify-send -u low "Layout americano caricato!" 
fi
echo "kmap=$kmap" > "$keymap_file"

