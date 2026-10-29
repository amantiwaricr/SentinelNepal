#!/bin/sh
# Reconnaissance exercise: a TCP connect scan of the first 1024 ports of the lab server,
# rate-limited so it cannot overwhelm anything.
. /lab/common.sh
echo "Scanning ports 1-1024 on $TARGET"
nmap -sT -Pn -p 1-1024 --max-rate 200 "$TARGET"
