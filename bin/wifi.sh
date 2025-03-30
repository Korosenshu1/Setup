#!/bin/bash
if nmcli connection show --active | grep -q wifi; then
	echo "🛜"
fi
