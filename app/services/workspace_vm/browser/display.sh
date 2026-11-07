#!/bin/bash
# consens.io workspace: starts the screen with its VNC server, a window
# manager and Chrome with its lasting profile, each unless it already runs.
# They outlive this command and the VM's short pauses; after a long sleep the
# VM has stopped them and the next call starts them again, sign-ins intact.
# Every daemon gets its own output and none of this script's descriptors
# (8>&-): an inherited pipe would keep the caller waiting, an inherited lock
# would block the next call. Neither listens on a network: the VNC server on
# a Unix socket in this folder (vnc.sock, mode 0600), which only the
# provider's user opens (relay.py); -rfbport -1 and -nolisten tcp leave no
# TCP port.
#
# All of it runs on the workbench, next to the agent's
# user, who must reach none of it (docs/agent-mode.md "Ein Rechner"):
# - Chrome has no debugging port (TCP on 127.0.0.1 would let every user of
#   the computer steer it and read its cookies): cdp.py starts it with
#   --remote-debugging-pipe and offers the protocol on cdp.sock, mode 0600 in
#   this folder, which lies in the provider's home (750, the agent is not in
#   its group).
# - The X server asks for a cookie (xauthority, 0600 here, new with each
#   start), so no other user's program draws, reads keys or takes pictures.
# - Chrome starts only on an X server of this user that holds its own
#   sockets (ours): X tries the abstract socket @/tmp/.X11-unix/X1 first,
#   and one the agent's user bound there would get Chrome's windows and the
#   user's keys. An X server whose socket is taken does not start, and this
#   script then starts no Chrome either. The agent's commands have a /tmp of
#   their own (agent-run), so the real one's sockets and locks are out of
#   their reach.
# - Every process this script looks for or ends is this user's (pgrep -u):
#   a process of the agent's user named like Chrome or the X server counts
#   for nothing.
#
# The screen is TigerVNC's X server (Xtigervnc, one process for screen and
# VNC). With Xvfb drawing, x11vnc found the changes by comparing the picture
# line by line (-noxdamage), and each picture waited for the view's next
# request. On a test Sprite with a scrolling page about
# half of what reached the view were half-drawn pictures: 13 whole pictures a
# second with 30 ms more between the user and the server, 9 with 60 ms.
# Xtigervnc knows what changed and sends without being asked (continuous
# updates, which noVNC asks for): 30 a second (-FrameRate 30) at about 5 MB/s
# after a few seconds of scrolling, also with 30 ms more; 15 to 23 with 60 ms.
# Without the limit it sent over 120 a second. No clipboard either way (the
# view's paste types keys) and no resizing by the viewer. A VM from before
# installs it once (install.sh) and its Xvfb, x11vnc and openbox make way here,
# Chrome first (its session keeps the tabs); never under --keep, which must
# not end a Chrome in use.
#
# It also mends a Chrome that is no longer usable (seen on Max's browser
# VM: a page load and the next connection ran into their time limits,
# Chrome died two minutes later, and the live view stayed black until the
# next call): a Chrome whose debugging pipe does not answer, or
# whose browser process is gone while children remain, is ended and started
# again; the profile keeps sign-ins and the session its tabs. --restart (from
# browser.py, after a call it could not finish) restarts it in any case;
# --keep (the live view's watch, relay.py) only starts a Chrome that is not
# running, never ends one the user may be using. chrome.log keeps earlier
# starts (each with its reason) up to about 1 MB.
dir="$HOME/.consens/browser"
here="$(cd "$(dirname "$0")" && pwd)"
profile="$dir/profile"
cdp="$dir/cdp.sock"
auth="$dir/xauthority"
mode="${1:-}"
me="$(id -u)"
mkdir -p "$profile/Default"
chmod 700 "$dir"
export DISPLAY=:1 XAUTHORITY="$auth"
exec 8>"$dir/display.lock"
flock 8
runs() { pgrep -u "$me" -f -- "$1" >/dev/null; }
# Every process of this profile's Chrome. The browser process is named as it
# was started, /usr/bin/google-chrome (the starter script execs Chrome under
# its own name); only its children (renderers, the zygote, the GPU process)
# are /opt/google/chrome/chrome, and they carry its --user-data-dir too.
# A check on the children alone failed: a Chrome counted
# as running while any child lived, the flags' restart ended only the
# children (Chrome died with "GPU process isn't usable"), and a Chrome whose
# children were gone got a second one started on the same profile. From the
# start of the command line, so cdp.py (whose own line names Chrome's) is
# not Chrome.
chrome="^([^ ]*/)?(google-chrome(-stable)?|chrome) .*--user-data-dir=$profile( |$)"
# cdp.py holding Chrome's pipe, whatever python3 is called.
hub="[^ ]*/cdp\.py $cdp( |$)"
# The browser process is the one without --type=.
browser_pid() {
  for pid in $(pgrep -u "$me" -f -- "$chrome"); do
    tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q -- " --type=" || { echo "$pid"; return; }
  done
}
# The target list needs Chrome's own main thread, unlike its version.
answers() { curl -s -m "${1:-5}" -o /dev/null --unix-socket "$cdp" "http://localhost/json/list"; }
# Every process of this profile ends before a new Chrome starts: two on one
# profile at once (seen when the flags changed) could damage it.
# cdp.py first: it ends Chrome with it.
stop_chrome() {
  pkill -TERM -u "$me" -f -- "$hub"
  pkill -TERM -u "$me" -f -- "$chrome"
  for _ in $(seq 50); do runs "$chrome" || runs "$hub" || return 0; sleep 0.1; done
  pkill -KILL -u "$me" -f -- "$hub" 2>/dev/null || true
  pkill -KILL -u "$me" -f -- "$chrome" 2>/dev/null || true
  for _ in $(seq 30); do runs "$chrome" || runs "$hub" || return 0; sleep 0.1; done
}
# The X server of this user, and whether it holds its sockets: the file
# /tmp/.X11-unix/X1 is this user's, and every stream socket bound to the
# name @/tmp/.X11-unix/X1 (listening or not yet) is this user's and there is
# one (xsocket.py asks the kernel whose each is, sock_diag). An X server
# never starts on a name another process holds ("Cannot establish any
# listening sockets", measured with Xvfb 21.1 and Xtigervnc 1.13), so a
# running one normally holds it; were it to listen without it, none of
# another user's may exist at the moment Chrome connects. Connections count
# for nothing (anyone may connect without the cookie: a loop of the agent's
# connections ended the user's Chrome), nor do other
# socket types (Linux keeps abstract names apart by type; a datagram socket
# of the agent's on the name did the same). The X server's own descriptors
# would not tell: Ubuntu 26.04's Xtigervnc, not dumpable, keeps them from
# its own user (test Sprite 2026-11-04: no Chrome ever started).
x_pid() { pgrep -u "$me" -x Xtigervnc | head -n 1; }
x_ours() {
  [ -n "$(x_pid)" ] || return 1
  [ -S /tmp/.X11-unix/X1 ] && [ "$(stat -c %u /tmp/.X11-unix/X1)" = "$me" ] || return 1
  python3 "$here/xsocket.py" "$me"
}
# A cookie only this user reads, new with each start of the X server.
new_cookie() {
  (umask 077 && python3 -c '
import os, struct, sys
field = lambda data: struct.pack(">H", len(data)) + data
with open(sys.argv[1], "wb") as handle:
    handle.write(struct.pack(">H", 0xFFFF) + field(b"") + field(b"1") + field(b"MIT-MAGIC-COOKIE-1")
                 + field(os.urandom(16)))' "$auth.new" && mv -f "$auth.new" "$auth")
}
# The old screen of a VM from before (Xvfb, x11vnc) and the openbox on it.
old="^(Xvfb :1|x11vnc -display :1) |^openbox( |$)"
if [ "$mode" != "--keep" ] && runs "^(Xvfb :1|x11vnc -display :1) "; then
  stop_chrome
  pkill -TERM -u "$me" -f -- "$old"
  for _ in $(seq 50); do runs "$old" || break; sleep 0.1; done
  pkill -KILL -u "$me" -f -- "$old" 2>/dev/null || true
  for _ in $(seq 30); do runs "$old" || break; sleep 0.1; done
fi
if [ -z "$(x_pid)" ] && ! runs "^Xvfb :1 "; then
  # A Chrome on a screen that went away goes too: it starts again on the new one.
  stop_chrome
  pkill -TERM -u "$me" -x openbox 2>/dev/null || true
  rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 "$dir/vnc.sock"
  new_cookie
  setsid nohup Xtigervnc :1 -auth "$auth" -geometry 1280x800 -depth 24 -rfbunixpath "$dir/vnc.sock" \
    -rfbunixmode 0600 -rfbport -1 -nolisten tcp -SecurityTypes None -AlwaysShared -AcceptSetDesktopSize=0 \
    -AcceptCutText=0 -SendCutText=0 -FrameRate 30 -desktop consens >"$dir/xvnc.log" 2>&1 </dev/null 8>&- &
  for _ in $(seq 50); do [ -e /tmp/.X11-unix/X1 ] && [ -S "$dir/vnc.sock" ] && break; sleep 0.1; done
fi
# --keep (the live view) never ends a Chrome: one that runs is connected already.
if ! x_ours; then
  [ "$mode" = "--keep" ] || stop_chrome
  echo "The browser's screen did not start (its socket is not its own)." >&2
  exit 1
fi
# The rules that hold whoever steers Chrome (harden.sh):
# Chrome's policy, openbox without menus, an xdg-open that opens nothing.
# Without them no Chrome starts, and one that runs (under older rules) ends.
if ! bash "$here/harden.sh" >"$dir/harden.log" 2>&1 </dev/null; then
  stop_chrome
  echo "The browser's rules could not be set." >&2
  exit 1
fi
if ! runs "^openbox( |$)"; then
  setsid nohup openbox >"$dir/openbox.log" 2>&1 </dev/null 8>&- &
fi
# WebGL without a graphics card: Chrome no longer falls back to software
# by itself, so maps, design tools and canvas apps did not start.
# A Chrome started with older flags is restarted once; the profile keeps
# sign-ins and the session its tabs. Which flags it has says the marker this
# script writes when it starts Chrome: Chrome rewrites its command line, so
# a search for a flag in it never matched, and Chrome restarted on every
# call. The rules' version counts as a flag: new rules restart Chrome once,
# so that it starts under them. pipe-1: Chrome behind cdp.py.
flags="webgl-1 pipe-1 rules-$(cat "$dir/hardened" 2>/dev/null)"
pid="$(browser_pid)"
why=""
if [ -n "$pid" ] && [ "$mode" != "--keep" ]; then
  if [ "$(cat "$dir/chrome-flags" 2>/dev/null)" != "$flags" ]; then why="new flags"
  elif [ "$mode" = "--restart" ]; then why="a call it could not finish"
  elif [ ! -S "$cdp" ] || ! runs "$hub" || { ! answers && ! answers; }; then why="no answer on its debugging pipe"
  fi
elif [ -z "$pid" ] && { runs "$chrome" || runs "$hub"; }; then
  why="its browser process was gone"
fi
[ -n "$why" ] && stop_chrome
started=""
if [ -z "$(browser_pid)" ]; then
  started=1
  # A Chrome the VM stopped leaves its lock behind; nothing else uses the profile.
  rm -f "$profile"/Singleton*
  # Continue where it left off: session cookies (sign-ins without "remember me") survive a restart.
  [ -f "$profile/Default/Preferences" ] || echo '{"session":{"restore_on_startup":1}}' >"$profile/Default/Preferences"
  log="$dir/chrome.log"
  [ "$(stat -c %s "$log" 2>/dev/null || echo 0)" -gt 1000000 ] && mv -f "$log" "$log.1"
  echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ) Chrome starts${why:+, restarted: $why}" >>"$log"
  rm -f "$cdp"
  setsid nohup python3 "$here/cdp.py" "$cdp" google-chrome --user-data-dir="$profile" \
    --no-first-run --no-default-browser-check --start-maximized \
    --disable-dev-shm-usage --hide-crash-restore-bubble --password-store=basic \
    --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader \
    >>"$log" 2>&1 </dev/null 8>&- &
  echo "$flags" >"$dir/chrome-flags"
fi
# A Chrome started here is ready once it answers; one that ran was asked
# above (and with --keep is not asked: a hung one there held the lock for
# 150 answers of 5 s). At most 15 s either way.
until=$((SECONDS + 15))
while [ "$SECONDS" -lt "$until" ]; do
  [ -S "$cdp" ] && runs "$hub" && [ -S "$dir/vnc.sock" ] && { [ -z "$started" ] || answers 2; } && exit 0
  sleep 0.1
done
echo "The browser did not start." >&2
exit 1
