#!/bin/bash

# Funzione per alzare il volume
increase_volume() {
    wpctl set-volume @DEFAULT_AUDIO_SINK@ 10%+
    pkill -RTMIN+2 dwmblocks
}

# Funzione per abbassare il volume
decrease_volume() {
    wpctl set-volume @DEFAULT_AUDIO_SINK@ 10%-
    pkill -RTMIN+2 dwmblocks
}

# Funzione per attivare/disattivare il mute
toggle_mute() {
    wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
    pkill -RTMIN+2 dwmblocks
}

# Gestione dei parametri passati allo script
case "$1" in
    up)
        increase_volume
        ;;
    down)
        decrease_volume
        ;;
    mute)
        toggle_mute
        ;;
esac

