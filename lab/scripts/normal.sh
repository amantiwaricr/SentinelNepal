#!/bin/sh
# Ordinary traffic: fetch a page every few seconds, forever (the container's default).
. /lab/common.sh
echo "Normal browsing of $TARGET (Ctrl+C to stop)"
while true; do
  curl -s -o /dev/null "http://$TARGET/" || true
  sleep 3
  curl -s -o /dev/null "http://$TARGET/about.html" || true
  sleep 4
done
