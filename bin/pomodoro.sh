#!/bin/bash

############################
# Configurazione
############################

study_minutes=30
short_break_minutes=5
long_break_minutes=15

study_time=$(( study_minutes * 60 ))
short_break_time=$(( short_break_minutes * 60 ))
long_break_time=$(( long_break_minutes * 60 ))

state_file="$HOME/.cache/pomodoro_state"
source "$state_file"
status_bar_file="$HOME/.cache/pomodoro_bar"
source "$status_bar_file"

############################
# Stato iniziale
############################

mode="study"
state="stopped"
remaining=$study_time
completed_sessions=0


############################
# Funzioni del programma 
############################

status_output() {
    	if [[ "$state" == "running" || "$state" == "paused" ]]; then
		case "$mode" in 
			study) icon=" ⏳";;
			short_break) icon=" ☕";;
			long_break) icon=" 🍵";;
		esac
		echo "$icon $(format_time "$remaining")"
	else
		echo ""
	fi
	pkill -RTMIN+3 dwmblocks
}

save_state() {
    cat > "$state_file" << EOF
mode="$mode"
state="$state"
remaining=$remaining
completed_sessions=$completed_sessions
EOF

	status_output > "$status_bar_file"
}

format_time() {
    local total=$1
    local m=$(( total / 60 ))
    local s=$(( total % 60 ))

    printf "%02d:%02d" "$m" "$s"
}

notify_end() {
    notify-send "Pomodoro" "$1"

    paplay /home/manuel/Audio/alarm.ogg \
        >/dev/null 2>&1 &
}

draw_screen() {

    clear

    echo "========================"
    echo "       POMODORO"
    echo "========================"
    echo
    echo "Modalità : $mode"
    echo "Stato    : $state"
    echo
    echo "Tempo rimanente : $(format_time "$remaining")"
    echo
    echo "(p) Pause"
    echo "(s) Skip"
    echo "(q) Stop"
    echo
}

next_mode() {

    case "$mode" in

        study)

            completed_sessions=$(( completed_sessions + 1 ))

            if (( completed_sessions % 3 == 0 )); then
                mode="long_break"
                remaining=$long_break_time
            else
                mode="short_break"
                remaining=$short_break_time
            fi
            ;;

        short_break|long_break)

            mode="study"
            remaining=$study_time
            ;;
    esac

    save_state
}

stop_timer() {

    state="stopped"

    case "$mode" in

        study)
            remaining=$study_time
            ;;

        short_break)
            remaining=$short_break_time
            ;;

        long_break)
            remaining=$long_break_time
            ;;
    esac

    save_state
}

reset_timer() {

    stop_timer

    echo
    echo "Timer resettato"

    sleep 1
}

skip_mode() {

    next_mode

    state="stopped"

    echo
    echo "Nuova modalità: $mode"

    sleep 1
}

run_timer() {

    state="running"

    while (( remaining > 0 )); do

        save_state

        draw_screen

        if read -rsn1 -t 1 choice; then

            case "$choice" in

                p)

                    state="paused"
                    save_state

                    echo
                    echo "Timer in pausa"
                    sleep 1

                    return
                    ;;

                s)

                    skip_mode
                    return
                    ;;

                q)

                    stop_timer
                    return
                    ;;
            esac
        fi

	#save_state

        ((remaining--))
    done

    state="stopped"

    case "$mode" in

        study)
            notify_end "Sessione di studio terminata"
            ;;

        short_break)
            notify_end "Pausa breve terminata"
            ;;

        long_break)
            notify_end "Pausa lunga terminata"
            ;;
    esac

    next_mode

    echo
    echo "Cambio modalità -> $mode"

    sleep 2
}

start_timer() {

    if [[ "$state" == "running" ]]; then
        echo
        echo "Il timer è già attivo"
        sleep 1
        return
    fi

    state="running"

    run_timer
}

main_menu() {

    while true; do

        clear

        echo "========================"
        echo "       POMODORO"
        echo "========================"
        echo
        echo "Modalità corrente : $mode"
        echo "Stato corrente    : $state"
        echo "Tempo             : $(format_time "$remaining")"
        echo
        echo "(1) Start / Resume"
        echo "(2) Reset"
        echo "(3) Skip"
        echo "(4) Exit"
        echo

        read -rp "Selezionare un'opzione: " choice

        case "$choice" in

            1)
                start_timer
                ;;

            2)
                reset_timer
                ;;

            3)
                skip_mode
                ;;

            4)
                clear
                exit 0
                ;;

            *)
                echo
                echo "Opzione non valida"
                sleep 1
                ;;
        esac
    done
}

main_menu
