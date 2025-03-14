#!/bin/bash
c=$(mpstat 1 1 | awk 'NR==4 {print 100 - $NF"%"}')
r=$(awk '/^MemTotal:/ {tot=$2} /^MemFree:/ {free=$2} /^Buffers:/ {buf=$2} /^Cached:/ {cache=$2} END {print (tot-free-buf-cache)*1024}' /proc/meminfo | numfmt --to=iec)
echo "⚙️ [$c, $r]"
