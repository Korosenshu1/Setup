#!/bin/sh
st -t calpopup -g 67x33 -e sh -c "
tput civis
cal -Y -m
read -n 1
tput cnorm
"
