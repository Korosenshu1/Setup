#!/bin/bash
mpstat 1 1 | awk 'NR==4 {print 100 - $NF"%"}'
