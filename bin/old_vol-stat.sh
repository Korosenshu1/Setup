#!/bin/sh

if [ "$(pulsemixer -l | awk '/^Sink:/ && /Default/' | awk -F 'Mute: ' '{print substr($2, 1, 1)}')" = "0" ]; then
	vol_perc=$(pulsemixer --get-volume | awk '{print ($1+$2)/2}')
    	echo "󰕾 $vol_perc%"
	vol_perc=$(echo $vol_perc | awk '{print $1/150*100}')
	notify-send -u low -h int:value:$vol_perc "Volume"
else
    	echo "$(pulsemixer --get-volume | awk '{print "󰖁",$1}')%"
	notify-send -u low -h string:bgcolor:"#ffffff" -i ~/.icons/mute.svg ""
fi
