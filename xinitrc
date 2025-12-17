picom &
nitrogen --restore &
redshift -c ~/.config/redshift/redshift.conf &
setxkbmap -option caps:swapescape,compose:ralt &
dunst &
xrdb -merge ~/.Xresources &
pactl set-source-mute @DEFAULT_SOURCE@ 1 &
dwmblocks &
~/.local/bin/sysinfo-daemon.sh &
~/.local/bin/netinfo-daemon.sh &
conky -c ~/.config/conky/todo.conf &
exec dwm
