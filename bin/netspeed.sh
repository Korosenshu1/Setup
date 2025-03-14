#!/bin/sh
INTERFACCIA="wlp0s20f3"  
RX1=$(cat /sys/class/net/$INTERFACCIA/statistics/rx_bytes)
TX1=$(cat /sys/class/net/$INTERFACCIA/statistics/tx_bytes)
sleep 1
RX2=$(cat /sys/class/net/$INTERFACCIA/statistics/rx_bytes)
TX2=$(cat /sys/class/net/$INTERFACCIA/statistics/tx_bytes)

RX_RATE=$(( (RX2 - RX1) / 1024 ))  # KB/s
TX_RATE=$(( (TX2 - TX1) / 1024 ))  # KB/s

if [ "$RX_RATE" -ge 1024 ]; then
RX_FORMAT=$(awk "BEGIN {printf \"%.2f MB/s\", $RX_RATE / 1024}")
else
RX_FORMAT="${RX_RATE} KB/s"
fi

if [ "$TX_RATE" -ge 1024 ]; then
TX_FORMAT=$(awk "BEGIN {printf \"%.2f MB/s\", $TX_RATE / 1024}")
else
TX_FORMAT="${TX_RATE} KB/s"
fi

echo "🔺$TX_FORMAT 🔻$RX_FORMAT"

