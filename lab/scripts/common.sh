#!/bin/sh
# Shared settings. Every script targets only the lab server on the internal lab network;
# there is deliberately no option to point them anywhere else.
TARGET=lab-server
if ! getent hosts "$TARGET" > /dev/null; then
  echo "lab-server is not reachable: run this inside the lab-client container" >&2
  exit 1
fi
