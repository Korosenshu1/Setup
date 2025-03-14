#!/bin/sh

audio_info=$(wpctl get-volume @DEFAULT_AUDIO_SINK@)
mute_status=$(echo $audio_info | awk '{print $3}')
vol_perc=$(echo $audio_info | awk '{print $2*100}')
if [ "$mute_status" = "[MUTED]" ]; then
    echo "🔇 $vol_perc%"
    notify-send -u low -h string:bgcolor:"#ffffff" -i ~/.icons/mute.svg ""
else
    echo "🔊 $vol_perc%"
    vol=$(echo $vol_perc | awk '{print $1*100/150}')
    notify-send -u low -h int:value:$vol "Volume"
fi

