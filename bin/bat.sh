#!/bin/bash

STATE_FILE="$HOME/.cache/dwmblocks_battery_state"
source "$STATE_FILE"

bat=$(acpi)
bat_perc=$(acpi -b | grep -oP '[0-9]+(?=%)')

if [ "$(echo $bat | awk '{print $3}')" = "Discharging," ]; then
    if [ $curr -eq 1 ]; then
        curr=0
        nc_alert=0
        notify-send -i ~/.icons/disconnected.png "Alimentazione scollegata!" "Il dispositivo verrà alimentato dalla batteria."
    fi

    if [ $bat_perc -le 20 ]; then
    	echo "🪫 $bat_perc%"
	    if [ $low_bat_alert -eq 0 ]; then
        	low_bat_alert=1
       		notify-send -u critical -i ~/.icons/low.png "Batteria scarica!" "La percentuale batteria è al 20%."
		paplay /home/manuel/Audio/not1.ogg
	    fi
    else
    	echo "🔋 $bat_perc%"
    fi

elif [ "$(echo $bat | awk '{print $3,$4}')" = "Not charging," ]; then 
    if [ $curr -eq 0 ]; then
	    curr=1
    fi
    if [ $nc_alert -eq 0 ]; then
        nc_alert=1
        notify-send -i ~/.icons/not-charging.png "Carica completa!" "Il dispositivo verrà solo alimentato."
    fi
    echo "⚡ $bat_perc% (not charg.)"

else
    if [ $curr -eq 0 ]; then
        curr=1
        low_bat_alert=0
        nc_alert=0
        notify-send -i ~/.icons/connected.png "Dispositivo in carica!" "La batteria si sta ricaricando."
    fi
    echo "⚡ $bat_perc%"
fi

# Salva i valori aggiornati nel file di stato
echo "curr=$curr" > "$STATE_FILE"
echo "low_bat_alert=$low_bat_alert" >> "$STATE_FILE"
echo "nc_alert=$nc_alert" >> "$STATE_FILE"
