#!/usr/bin/env bash

set -u

# ============================================================
# CONFIGURAZIONE
# ============================================================

SCAN_INTERVAL=2
ROFI_CONFIG="$HOME/.config/rofi/wifi.rasi"

# ============================================================
# AVVIO
# ============================================================

# Se ROFI_RETV non è definita, siamo stati chiamati da Waybar.
# Avviamo quindi:
#
#   1. un processo in background che richiede periodicamente
#      una nuova scansione Wi-Fi
#   2. Rofi in script mode
#
# Il processo bash rimane in vita fino alla chiusura di Rofi,
# così possiamo ripulire il processo scanner alla fine.

if [[ -z "${ROFI_RETV+x}" ]]; then

    # --------------------------------------------------------
    # Processo di scansione in background.
    #
    # Questo NON interagisce con Rofi e quindi non può bloccarlo.
    # --------------------------------------------------------

    (
        while true; do
            nmcli device wifi rescan >/dev/null 2>&1
            sleep "$SCAN_INTERVAL"
        done
    ) &

    SCANNER_PID=$!

    # Assicuriamoci di terminare lo scanner quando Rofi chiude.
    trap 'kill "$SCANNER_PID" 2>/dev/null; wait "$SCANNER_PID" 2>/dev/null; exit' EXIT INT TERM

    # --------------------------------------------------------
    # Avvia Rofi.
    # --------------------------------------------------------

    rofi \
        -config "$ROFI_CONFIG" \
        -show wifi \
        -modes "wifi:$0" \
        -hover-select \
        -me-select-entry '' \
        -me-accept-entry MousePrimary \
        -wayland-layer overlay

    exit 0
fi


# ============================================================
# FUNZIONI
# ============================================================

get_networks() {

    # --------------------------------------------------------
    # IMPORTANTE:
    #
    # Qui NON usiamo --rescan yes.
    #
    # Leggiamo semplicemente la lista AP che NetworkManager
    # ha già a disposizione.
    #
    # Questo comando deve essere rapido e non blocca Rofi
    # aspettando una scansione Wi-Fi.
    # --------------------------------------------------------

    nmcli \
        -t \
        -e yes \
        -f IN-USE,SSID,SIGNAL,SECURITY \
        device wifi list \
        --rescan no |
    while IFS= read -r line; do

        # ----------------------------------------------------
        # Parsing robusto del formato terse di nmcli.
        # Gestiamo anche ':' presenti nell'SSID.
        # ----------------------------------------------------

        fields=()
        field=""
        escaped=0

        for ((i = 0; i < ${#line}; i++)); do

            char="${line:i:1}"

            if (( escaped )); then
                field+="$char"
                escaped=0

            elif [[ "$char" == '\' ]]; then
                escaped=1

            elif [[ "$char" == ':' ]]; then
                fields+=("$field")
                field=""

            else
                field+="$char"
            fi

        done

        fields+=("$field")

        # ----------------------------------------------------
        # IN-USE / SSID / SIGNAL / SECURITY
        # ----------------------------------------------------

        (( ${#fields[@]} < 4 )) && continue

        inuse="${fields[0]}"
        ssid="${fields[1]}"
        signal="${fields[2]}"
        security="${fields[3]}"

        [[ -z "$ssid" ]] && continue

        # ----------------------------------------------------
        # Icona rete attiva
        # ----------------------------------------------------

        if [[ "$inuse" == "*" ]]; then
            active_icon="●"
        else
            active_icon=" "
        fi

        # ----------------------------------------------------
        # Icona sicurezza
        # ----------------------------------------------------

        if [[ -n "$security" && "$security" != "--" ]]; then
            security_icon=""
        else
            security_icon=" "
        fi

        # ----------------------------------------------------
        # BARS
        # ----------------------------------------------------

        if (( signal >= 80 )); then
            bars="▂▄▆█"
        elif (( signal >= 60 )); then
            bars="▂▄▆_"
        elif (( signal >= 40 )); then
            bars="▂▄__"
        elif (( signal >= 20 )); then
            bars="▂___"
        else
            bars="____"
        fi

        # ----------------------------------------------------
        # info contiene il vero SSID.
        #
        # In questo modo il testo visualizzato può avere
        # formattazione arbitraria senza doverlo riparsare
        # quando l'utente seleziona una rete.
        # ----------------------------------------------------

        printf '%s  %s  %-32s %s %3s%%\0info\x1f%s\n' \
            "$active_icon" \
            "$security_icon" \
            "$ssid" \
            "$bars" \
            "$signal" \
            "$ssid"

    done
}


connect_network() {

    local ssid="$1"
    local password

    # --------------------------------------------------------
    # Prima prova:
    #
    # - rete aperta
    # - profilo NetworkManager già presente
    #
    # In questi casi non serve chiedere la password.
    # --------------------------------------------------------

    if nmcli device wifi connect "$ssid" >/dev/null 2>&1; then
        exit 0
    fi

    # --------------------------------------------------------
    # Password.
    # --------------------------------------------------------

    password="$(
        rofi \
            -config "$ROFI_CONFIG" \
            -dmenu \
            -password \
            -p "Password" \
            -mesg "$ssid" \
            -wayland-layer overlay
    )"

    [[ -z "$password" ]] && exit 0

    # --------------------------------------------------------
    # Connessione.
    # --------------------------------------------------------

    if nmcli device wifi connect \
            "$ssid" \
            password "$password" \
            >/dev/null 2>&1; then

        exit 0

    else

        rofi \
            -config "$ROFI_CONFIG" \
            -e "Impossibile connettersi a: $ssid" \
            -wayland-layer overlay

    fi
}


# ============================================================
# SCRIPT MODE DI ROFI
# ============================================================

case "${ROFI_RETV}" in

    # --------------------------------------------------------
    # 0 = apertura iniziale
    # --------------------------------------------------------

    0)

        printf '\0prompt\x1fWi-Fi\n'
        printf '\0message\x1fAggiornamento automatico ogni %ss\n' \
            "$SCAN_INTERVAL"

        printf '\0use-hot-keys\x1ftrue\n'
        printf '\0no-custom\x1ftrue\n'

        get_networks

        ;;

    # --------------------------------------------------------
    # 10 = custom keybinding #1
    #
    # Viene usato dal timeout di Rofi per aggiornare la lista.
    # --------------------------------------------------------

    10)

        printf '\0keep-selection\x1ftrue\n'
        printf '\0keep-filter\x1ftrue\n'

        get_networks

        ;;

    # --------------------------------------------------------
    # 1 = voce selezionata
    # --------------------------------------------------------

    1)

        if [[ -n "${ROFI_INFO:-}" ]]; then
            connect_network "$ROFI_INFO"
        fi

        ;;

esac
