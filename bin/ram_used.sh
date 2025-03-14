#!/bin/bash
awk '/^MemTotal:/ {tot=$2} /^MemFree:/ {free=$2} /^Buffers:/ {buf=$2} /^Cached:/ {cache=$2} END {print (tot-free-buf-cache)*1024}' /proc/meminfo | numfmt --to=iec
