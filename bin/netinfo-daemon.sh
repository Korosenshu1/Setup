#!/bin/sh
# netinfo-daemon: aggiorna in /tmp/netinfo_cache i dati di rete ogni secondo

CACHE="/tmp/netinfo_cache"

# Rileva automaticamente l'interfaccia di rete attiva
get_iface() {
    # Trova la prima interfaccia connessa (esclude loopback)
    ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}' | head -n1
}

#IFACE=$(get_iface)
#[ -z "$IFACE" ] && echo "NoNet" > "$CACHE" && exit 0
IFACE="wlp0s20f3"

# Inizializza contatori
RX_PREV=$(cat /sys/class/net/$IFACE/statistics/rx_bytes)
TX_PREV=$(cat /sys/class/net/$IFACE/statistics/tx_bytes)

while true; do
    sleep 1
    RX_CUR=$(cat /sys/class/net/$IFACE/statistics/rx_bytes)
    TX_CUR=$(cat /sys/class/net/$IFACE/statistics/tx_bytes)

    RX_DIFF=$((RX_CUR - RX_PREV))
    TX_DIFF=$((TX_CUR - TX_PREV))

    RX_PREV=$RX_CUR
    TX_PREV=$TX_CUR

    # Converti in unità leggibili (KB/s o MB/s)
    RX_HUMAN=$(awk "BEGIN {v=$RX_DIFF/1024; s=\"KB/s\"; if(v>=1024){v/=1024; s=\"MB/s\"}; printf \"%.1f %s\", v, s}")
    TX_HUMAN=$(awk "BEGIN {v=$TX_DIFF/1024; s=\"KB/s\"; if(v>=1024){v/=1024; s=\"MB/s\"}; printf \"%.1f %s\", v, s}")

    echo "🔺$TX_HUMAN 🔻$RX_HUMAN" > "$CACHE"
done

