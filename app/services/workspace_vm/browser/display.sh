#!/bin/bash
# consens.io browser VM: starts the screen with its VNC server, a window
# manager and Chrome with its lasting profile, each unless it already runs.
# They outlive this command and the VM's short pauses; after a long sleep the
# VM has stopped them and the next call starts them again, sign-ins intact.
# Every daemon gets its own output and none of this script's descriptors
# (8>&-): an inherited pipe would keep the caller waiting, an inherited lock
# would block the next call. CDP listens on 127.0.0.1 only, the VNC server on
# no network at all: a Unix socket in this folder (vnc.sock, mode 0600), which
# only the provider's user opens (relay.py); -rfbport -1 and -nolisten tcp
# leave no TCP port (test Sprite 2026-11-02).
#
# The screen is TigerVNC's X server since 2026-11-02 (Xtigervnc, one process
# for screen and VNC). Until then Xvfb drew and x11vnc found the changes by
# comparing the picture line by line (-noxdamage), and each picture waited
# for the view's next request. On a test Sprite with a scrolling page about
# half of what reached the view were half-drawn pictures: 13 whole pictures a
# second with 30 ms more between the user and the server, 9 with 60 ms.
# Xtigervnc knows what changed and sends without being asked (continuous
# updates, which noVNC asks for): 30 a second (-FrameRate 30) at about 5 MB/s
# after a few seconds of scrolling, also with 30 ms more; 15 to 23 with 60 ms.
# Without the limit it sent over 120 a second. No clipboard either way (the
# view's paste types keys) and no resizing by the viewer. A VM from before
# installs it once (setup.sh) and its Xvfb, x11vnc and openbox make way here,
# Chrome first (its session keeps the tabs); never under --keep, which must
# not end a Chrome in use.
#
# Since 2026-10-28 it also mends a Chrome that is no longer usable (Max's
# browser VM, 2026-10-28: a page load and the next connection ran into their
# time limits, Chrome died two minutes later, and the live view stayed black
# until the next call): a Chrome whose debugging port does not answer, or
# whose browser process is gone while children remain, is ended and started
# again; the profile keeps sign-ins and the session its tabs. --restart (from
# browser.py, after a call it could not finish) restarts it in any case;
# --keep (the live view's watch, relay.py) only starts a Chrome that is not
# running, never ends one the user may be using. chrome.log keeps earlier
# starts (each with its reason) up to about 1 MB.
dir="$HOME/.consens/browser"
profile="$dir/profile"
mode="${1:-}"
mkdir -p "$profile/Default"
export DISPLAY=:1
exec 8>"$dir/display.lock"
flock 8
runs() { pgrep -f -- "$1" >/dev/null; }
listens() { ss -ltn 2>/dev/null | grep -q "127.0.0.1:$1 "; }
# Every process of this profile's Chrome. The browser process is named as it
# was started, /usr/bin/google-chrome (the starter script execs Chrome under
# its own name); only its children (renderers, the zygote, the GPU process)
# are /opt/google/chrome/chrome, and they carry its --user-data-dir too.
# Until 2026-10-28 the check matched the children alone: a Chrome counted
# as running while any child lived, the flags' restart ended only the
# children (Chrome died with "GPU process isn't usable"), and a Chrome whose
# children were gone got a second one started on the same profile.
chrome="(^|/)(google-chrome(-stable)?|chrome) .*--user-data-dir=$profile( |$)"
# The browser process is the one without --type=.
browser_pid() {
  for pid in $(pgrep -f -- "$chrome"); do
    tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q -- " --type=" || { echo "$pid"; return; }
  done
}
# The target list needs Chrome's own main thread, unlike its version.
answers() { curl -s -m 5 -o /dev/null "http://127.0.0.1:9222/json/list"; }
# Every process of this profile ends before a new Chrome starts: two on one
# profile at once (seen 2026-10-28 when the flags changed) could damage it.
stop_chrome() {
  pkill -TERM -f -- "$chrome"
  for _ in $(seq 50); do runs "$chrome" || return 0; sleep 0.1; done
  pkill -KILL -f -- "$chrome" 2>/dev/null || true
  for _ in $(seq 30); do runs "$chrome" || return 0; sleep 0.1; done
}
# The screen of a VM from before 2026-11-02 and the openbox on it.
old="^(Xvfb :1|x11vnc -display :1) |^openbox( |$)"
if [ "$mode" != "--keep" ] && runs "^(Xvfb :1|x11vnc -display :1) "; then
  stop_chrome
  pkill -TERM -f -- "$old"
  for _ in $(seq 50); do runs "$old" || break; sleep 0.1; done
  pkill -KILL -f -- "$old" 2>/dev/null || true
  for _ in $(seq 30); do runs "$old" || break; sleep 0.1; done
fi
if ! runs "^Xtigervnc :1 " && ! runs "^Xvfb :1 "; then
  rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 "$dir/vnc.sock"
  setsid nohup Xtigervnc :1 -geometry 1280x800 -depth 24 -rfbunixpath "$dir/vnc.sock" -rfbunixmode 0600 -rfbport -1 \
    -nolisten tcp -SecurityTypes None -AlwaysShared -AcceptSetDesktopSize=0 -AcceptCutText=0 -SendCutText=0 \
    -FrameRate 30 -desktop consens >"$dir/xvnc.log" 2>&1 </dev/null 8>&- &
  for _ in $(seq 50); do [ -e /tmp/.X11-unix/X1 ] && [ -S "$dir/vnc.sock" ] && break; sleep 0.1; done
fi
# The rules that hold whoever steers Chrome (harden.sh, since 2026-10-30):
# Chrome's policy, openbox without menus, an xdg-open that opens nothing.
# Without them no Chrome starts, and one that runs (under older rules) ends.
if ! bash "$(dirname "$0")/harden.sh" >"$dir/harden.log" 2>&1 </dev/null; then
  stop_chrome
  echo "The browser's rules could not be set." >&2
  exit 1
fi
if ! runs "^openbox"; then
  setsid nohup openbox >"$dir/openbox.log" 2>&1 </dev/null 8>&- &
fi
# WebGL without a graphics card: Chrome no longer falls back to software
# by itself, so maps, design tools and canvas apps did not start (2026-10-28).
# A Chrome started with older flags is restarted once; the profile keeps
# sign-ins and the session its tabs. Which flags it has says the marker this
# script writes when it starts Chrome: Chrome rewrites its command line, so
# a search for a flag in it never matched, and Chrome restarted on every call
# (test Sprite 2026-10-28). The rules' version counts as a flag: new rules
# restart Chrome once, so that it starts under them.
flags="webgl-1 rules-$(cat "$dir/hardened" 2>/dev/null)"
pid="$(browser_pid)"
why=""
if [ -n "$pid" ] && [ "$mode" != "--keep" ]; then
  if [ "$(cat "$dir/chrome-flags" 2>/dev/null)" != "$flags" ]; then why="new flags"
  elif [ "$mode" = "--restart" ]; then why="a call it could not finish"
  elif ! listens 9222 || { ! answers && ! answers; }; then why="no answer on its debugging port"
  fi
elif [ -z "$pid" ] && runs "$chrome"; then
  why="its browser process was gone"
fi
[ -n "$why" ] && stop_chrome
if [ -z "$(browser_pid)" ]; then
  # A Chrome the VM stopped leaves its lock behind; nothing else uses the profile.
  rm -f "$profile"/Singleton*
  # Continue where it left off: session cookies (sign-ins without "remember me") survive a restart.
  [ -f "$profile/Default/Preferences" ] || echo '{"session":{"restore_on_startup":1}}' >"$profile/Default/Preferences"
  log="$dir/chrome.log"
  [ "$(stat -c %s "$log" 2>/dev/null || echo 0)" -gt 1000000 ] && mv -f "$log" "$log.1"
  echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ) Chrome starts${why:+, restarted: $why}" >>"$log"
  setsid nohup google-chrome --user-data-dir="$profile" --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port=9222 --no-first-run --no-default-browser-check --start-maximized \
    --disable-dev-shm-usage --hide-crash-restore-bubble --password-store=basic \
    --use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader \
    >>"$log" 2>&1 </dev/null 8>&- &
  echo "$flags" >"$dir/chrome-flags"
fi
for _ in $(seq 150); do listens 9222 && [ -S "$dir/vnc.sock" ] && exit 0; sleep 0.1; done
echo "The browser did not start." >&2
exit 1
