#!/usr/bin/env bash

set -u

ROFI_CONFIG="$HOME/.config/rofi/bluetooth.rasi"

# -------------------------------------------------------------------
# Avvio
# -------------------------------------------------------------------

if [[ -z "${ROFI_RETV+x}" ]]; then

    # Un unico bluetoothctl rimane attivo per tutta la durata
    # del menu e mantiene la discovery attiva.
    coproc BTCTL {
        bluetoothctl >/dev/null 2>&1
    }

    BTCTL_FD="${BTCTL[1]}"
    BTCTL_PID="$BTCTL_PID"

    # Inizializza controller, agent e scansione.
    printf '%s\n' \
        "power on" \
        "agent on" \
        "default-agent" \
        "scan on" \
        >&"$BTCTL_FD"

    cleanup() {
        printf '%s\n' \
            "scan off" \
            "quit" \
            >&"$BTCTL_FD" 2>/dev/null || true

        kill "$BTCTL_PID" 2>/dev/null || true
        wait "$BTCTL_PID" 2>/dev/null || true
    }

    trap cleanup EXIT INT TERM

    rofi \
        -config "$ROFI_CONFIG" \
        -show bluetooth \
        -modes "bluetooth:$0" \
        -hover-select \
        -me-select-entry '' \
        -me-accept-entry MousePrimary \
        -wayland-layer overlay

    exit 0
fi


# -------------------------------------------------------------------
# Ritorna 1 se MAC è presente nell'output di bluetoothctl devices
# -------------------------------------------------------------------

device_in_list() {
    local mac="$1"
    shift

    printf '%s\n' "$@" |
        grep -Fq "Device $mac "
}


# -------------------------------------------------------------------
# Elenco dispositivi
# -------------------------------------------------------------------

get_devices() {

    local all_devices
    local paired_devices
    local connected_devices

    all_devices="$(bluetoothctl devices 2>/dev/null)"
    paired_devices="$(bluetoothctl devices Paired 2>/dev/null)"
    connected_devices="$(bluetoothctl devices Connected 2>/dev/null)"

    [[ -z "$all_devices" ]] && return 0

    while IFS= read -r line; do

        [[ "$line" =~ ^Device[[:space:]]+([0-9A-Fa-f:]{17})[[:space:]]*(.*)$ ]] || continue

        mac="${BASH_REMATCH[1]}"
        name="${BASH_REMATCH[2]}"

        [[ -z "$name" ]] && name="$mac"

        # -----------------------------------------------------------
        # Stato
        # -----------------------------------------------------------

        if grep -Fq "Device $mac " <<< "$connected_devices"; then
            priority=0
            icon="●"
            state="connesso"

        elif grep -Fq "Device $mac " <<< "$paired_devices"; then
            priority=1
            icon="○"
            state="associato"

        else
            priority=2
            icon="·"
            state="rilevato"
        fi

        # -----------------------------------------------------------
        # Batteria: solo dispositivi connessi
        # -----------------------------------------------------------

        battery=""

        if [[ "$priority" == 0 ]]; then
            battery="$(
                bluetoothctl info "$mac" 2>/dev/null |
                sed -n 's/^[[:space:]]*Battery Percentage:.*(\([0-9]\+\)).*$/\1/p' |
                head -n1
            )"
        fi

        extra="$state"

        [[ -n "$battery" ]] &&
            extra+="  ${battery}%"

        # priority viene usato solo internamente per ordinare.
        printf '%d\t%s  %-32s  %s\0info\x1f%s\n' \
            "$priority" \
            "$icon" \
            "$name" \
            "$extra" \
            "$mac"

    done <<< "$all_devices" |
        sort -t$'\t' -k1,1 -k2,2f |
        cut -f2-
}

# -------------------------------------------------------------------
# Connessione / pairing
# -------------------------------------------------------------------

connect_device() {

    local mac="$1"

    # ---------------------------------------------------------------
    # Se è già connesso → disconnetti
    # ---------------------------------------------------------------

    if bluetoothctl devices Connected 2>/dev/null |
        grep -Fq "Device $mac "; then

        bluetoothctl disconnect "$mac" >/dev/null 2>&1
        exit 0
    fi

    # ---------------------------------------------------------------
    # Se è già paired → connetti
    # ---------------------------------------------------------------

    if bluetoothctl devices Paired 2>/dev/null |
        grep -Fq "Device $mac "; then

        if bluetoothctl connect "$mac" >/dev/null 2>&1; then
            exit 0
        fi

    else

        # -----------------------------------------------------------
        # Nuovo dispositivo → pairing
        #
        # bluetoothctl pair effettua pairing, trust e connect.
        # -----------------------------------------------------------

        if bluetoothctl pair "$mac" >/dev/null 2>&1; then
            exit 0
        fi

    fi

    # ---------------------------------------------------------------
    # Errore
    # ---------------------------------------------------------------

    rofi \
        -config "$ROFI_CONFIG" \
        -e "Impossibile connettersi al dispositivo" \
        -wayland-layer overlay

    exit 0
}


# -------------------------------------------------------------------
# Rofi script mode
# -------------------------------------------------------------------

case "${ROFI_RETV}" in

    # ===============================================================
    # Apertura iniziale
    # ===============================================================

    0)

        printf '\0prompt\x1fBluetooth\n'
        printf '\0message\x1fScansione attiva\n'

        printf '\0use-hot-keys\x1ftrue\n'
        printf '\0no-custom\x1ftrue\n'

        get_devices

        ;;


    # ===============================================================
    # Refresh automatico
    # ===============================================================

    10)

        printf '\0keep-selection\x1ftrue\n'
        printf '\0keep-filter\x1ftrue\n'
        printf '\0message\x1fScansione attiva\n'

        get_devices

        ;;


    # ===============================================================
    # Selezione dispositivo
    # ===============================================================

    1)

        if [[ -n "${ROFI_INFO:-}" ]]; then
            connect_device "$ROFI_INFO"
        fi

        ;;

esac
