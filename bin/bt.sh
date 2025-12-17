#!/bin/bash
if bluetoothctl devices Connected | grep -q .; then 
	echo " 🔷"
fi

# conta le linee di output
#linee=$(bluetoothctl devices Connected | wc -l)

# se sono più di 3, c'è almeno un dispositivo connesso (oltre al messaggio iniziale)
#if [ "$linee" -gt 3 ]; then
#    echo " 🔷"
#fi

