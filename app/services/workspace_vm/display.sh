#!/bin/bash
# consens.io workspace: starts the screen (Xvfb), a window manager, Chrome
# with its lasting profile and the VNC server, each unless it already runs.
# They outlive this command and the VM's short pauses; after a long sleep the
# VM has stopped them and the next call starts them again, sign-ins intact.
# Every daemon gets its own output and none of this script's descriptors
# (8>&-): an inherited pipe would keep the caller waiting, an inherited lock
# would block the next call.
dir="$HOME/.consens/browser"
profile="$dir/profile"
mkdir -p "$profile/Default"
export DISPLAY=:1
exec 8>"$dir/display.lock"
flock 8
runs() { pgrep -f -- "$1" >/dev/null; }
listens() { ss -ltn 2>/dev/null | grep -q "127.0.0.1:$1 "; }
if ! runs "^Xvfb :1 "; then
  rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
  setsid nohup Xvfb :1 -screen 0 1280x800x24 -nolisten tcp >"$dir/xvfb.log" 2>&1 </dev/null 8>&- &
  for _ in $(seq 50); do [ -e /tmp/.X11-unix/X1 ] && break; sleep 0.1; done
fi
if ! runs "^openbox"; then
  setsid nohup openbox >"$dir/openbox.log" 2>&1 </dev/null 8>&- &
fi
if ! runs "^/opt/google/chrome/chrome .*user-data-dir=$profile"; then
  # A Chrome the VM stopped leaves its lock behind; nothing else uses the profile.
  rm -f "$profile"/Singleton*
  # Continue where it left off: session cookies (sign-ins without "remember me") survive a restart.
  [ -f "$profile/Default/Preferences" ] || echo '{"session":{"restore_on_startup":1}}' >"$profile/Default/Preferences"
  setsid nohup google-chrome --user-data-dir="$profile" --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port=9222 --no-first-run --no-default-browser-check --start-maximized \
    --disable-dev-shm-usage --hide-crash-restore-bubble --password-store=basic \
    >"$dir/chrome.log" 2>&1 </dev/null 8>&- &
fi
if ! runs "^x11vnc -display :1 "; then
  setsid nohup x11vnc -display :1 -localhost -rfbport 5900 -shared -forever -nopw -quiet -noxdamage \
    >"$dir/vnc.log" 2>&1 </dev/null 8>&- &
fi
for _ in $(seq 150); do listens 9222 && listens 5900 && exit 0; sleep 0.1; done
echo "The browser did not start." >&2
exit 1
