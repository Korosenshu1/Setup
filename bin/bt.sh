#!/bin/bash
if bluetoothctl devices Connected | grep -q .; then 
	echo " 🔷"
fi

