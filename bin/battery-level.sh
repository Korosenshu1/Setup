#!/bin/sh

BAT=$(< /sys/class/power_supply/BAT0/capacity)

case $BAT in
	20) 
		notify-send -u low -i battery-caution "[\!] Batteria scarica" "Livello batteria al ${BAT}%" && paplay ~/Audio/not1.ogg
		;;
	10) 
		notify-send -u normal -i battery-caution "[\!] Batteria scarica" "Livello batteria al ${BAT}%" && paplay ~/Audio/not1.ogg
		;;
	5) 
		notify-send -u critical -i battery-caution "[\!] Batteria scarica" "Livello batteria al ${BAT}%" && paplay ~/Audio/not1.ogg
		;;
esac	

sleep 2
