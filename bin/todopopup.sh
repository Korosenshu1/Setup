#!/bin/sh
st -t calpopup -g 80x30 -e sh -c "
tput civis
cat ~/todo
read -n 1
tput cnorm
"
