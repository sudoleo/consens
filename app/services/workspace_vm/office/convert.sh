#!/bin/bash
# consens.io office converter: one Office file on stdin; on stdout a tar with
# its PDF (in.pdf), an overview of its first pages (pages.png) and their
# count (pages.txt) (agent_office.render). Run as root by the provider's
# user. Each conversion takes one of SLOTS places (a lock in /run) and runs
# LibreOffice and its helpers as that place's own user, office0 to office2,
# in a folder of this conversion alone; before and after, every process and
# file of that user goes. Conversions side by side never touch each other
# (until 2026-11-01 they shared one user, and the first to finish ended the
# others, live probe), and a file never meets another account's.
#   convert.sh <extension> <seconds> <overview pages>
#   convert.sh clean    only the clean-up of every free place (agent_office.sweep)
# Exit 2: a type it does not take, 3: LibreOffice made no PDF of the file,
# 4: every place is taken, 5: LibreOffice took longer than <seconds>.
# Every step has its own limit; together they stay below the server's
# (agent_office.RUN_SECONDS), so the script, not the server, ends a slow one.
set -u
# A folder the place's users can enter, whoever started this: LibreOffice
# in one they cannot (the provider's home) ends at once (live probe).
cd / || exit 1
ext=$1
seconds=${2:-}
shown=${3:-}
slots=3
# Each command of a place runs with at most this much address space
# (bytes; prlimit takes no units). A conversion takes 0.5 to 0.6 GB of it
# and 150 to 210 MB resident (live probe 2026-11-01); three at once stay
# within the VM's 8 GB without swap, and a file that would take more (a zip
# bomb, a page of metres in sheet.py) ends its own conversion instead of
# the memory of all three. The VM's cgroup takes no limits of its own.
memory=2147483648
case "$ext" in
  clean|pptx|ppt|odp|docx|doc|odt|rtf|xlsx|xls|ods) ;;
  *) echo "Not an Office file this converter takes: .$ext" >&2; exit 2 ;;
esac
install -d -m 0700 /run/consens-office || exit 1
dir=""
slot=""
as_user() {
  # The places' locks stay with this script, never with what it starts.
  local who=$1
  shift
  prlimit --as="$memory" -- setpriv --reuid="$who" --regid="$who" --init-groups --no-new-privs -- \
    env -i HOME="${dir:-/nonexistent}" PATH=/usr/bin:/bin LANG=C.UTF-8 "$@" 8>&- 9>&-
}
clean() {
  # Every process of place user $1, also one that keeps forking (kill -1
  # as that user reaches all of them), then every file it owns.
  as_user "$1" kill -s KILL -- -1 2>/dev/null
  pkill -KILL -u "$1" 2>/dev/null
  find /tmp /var/tmp /dev/shm -xdev -user "$1" -exec rm -rf -- {} + 2>/dev/null
}
# What a conversion stopped with SIGKILL left (its trap never ran: Stop,
# the server's timeout, a deploy) goes before the next account's file
# arrives, on every place that is free now (its lock held for the moment)
# and on the one this conversion takes. The places beyond the first are
# seldom used: their leftovers would otherwise stay for days.
clean_free() {
  local other
  for other in $(seq 0 $((slots - 1))); do
    if [ "$other" = "$slot" ]; then continue; fi
    exec 8>"/run/consens-office/slot$other.lock"
    if flock -n 8; then clean "office$other"; fi
    exec 8>&-
  done
}
if [ "$ext" = clean ]; then
  clean_free
  exit 0
fi
# A place another conversion's clean_free holds for a moment is free again
# right after.
for attempt in 1 2 3; do
  for candidate in $(seq 0 $((slots - 1))); do
    exec 9>"/run/consens-office/slot$candidate.lock"
    if flock -n 9; then
      slot=$candidate
      break 2
    fi
  done
  sleep 0.3
done
if [ -z "$slot" ]; then
  echo "The converter is busy." >&2
  exit 4
fi
user=office$slot
as_office() { as_user "$user" "$@"; }
cleanup() {
  clean "$user"
  if [ -n "$dir" ]; then rm -rf -- "$dir"; fi
}
clean_free
cleanup
trap cleanup EXIT
dir=$(mktemp -d /tmp/office.XXXXXXXXXX) || exit 1
chown "$user:$user" "$dir"
chmod 700 "$dir"

as_office sh -c 'cat > "$1"' sh "$dir/in.$ext" || exit 1
as_office timeout --kill-after=5 "$seconds" soffice --headless --norestore --nolockcheck \
  "-env:UserInstallation=file://$dir/profile" --convert-to pdf --outdir "$dir" "$dir/in.$ext" >/dev/null 2>&1
status=$?
if [ ! -s "$dir/in.pdf" ]; then
  if [ "$status" = 124 ] || [ "$status" = 137 ]; then
    echo "LibreOffice took longer than $seconds seconds for this file." >&2
    exit 5
  fi
  echo "LibreOffice could not turn the file into a PDF (damaged, protected or not what its name says; status $status)." >&2
  exit 3
fi
# Written by the place's user, as everything in its folder: a link planted
# there never leads root's writes anywhere.
as_office sh -c 'timeout 10 pdfinfo "$1" 2>/dev/null | sed -n "s/^Pages:[[:space:]]*//p" > "$2"' \
  sh "$dir/in.pdf" "$dir/pages.txt"
as_office timeout 20 pdftoppm -r 40 -png -l "$shown" "$dir/in.pdf" "$dir/page" >/dev/null 2>&1 || exit 1
as_office timeout 20 /usr/bin/python3 /usr/local/lib/consens/office/sheet.py "$dir" || exit 1
tar -C "$dir" -cf - in.pdf pages.png pages.txt
