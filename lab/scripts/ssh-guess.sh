#!/bin/sh
# Password-guessing exercise: 15 SSH logins with wrong passwords (no account can succeed).
. /lab/common.sh
echo "15 failing SSH logins to $TARGET"
i=1
while [ "$i" -le 15 ]; do
  sshpass -p "wrong-password-$i" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 "labuser@$TARGET" true 2>/dev/null || true
  i=$((i + 1))
done
echo "done"
