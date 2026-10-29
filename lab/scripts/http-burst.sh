#!/bin/sh
# Burst exercise: 300 quick web requests (a small, rate-limited stand-in for flooding).
. /lab/common.sh
echo "300 requests to $TARGET"
i=1
while [ "$i" -le 300 ]; do
  curl -s -o /dev/null --max-time 2 "http://$TARGET/" &
  if [ $((i % 20)) -eq 0 ]; then wait; fi
  i=$((i + 1))
done
wait
echo "done"
