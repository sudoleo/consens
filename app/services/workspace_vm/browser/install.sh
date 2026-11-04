#!/bin/bash
# consens.io workspace: installs the browser's screen, its VNC server, a
# window manager, fonts and Playwright once, as the provider's user with sudo
# (agent_browser.py; setup.sh, which runs as root with every new version,
# installs Chrome itself). Called by browser.py and relay.py; the lock makes
# a second caller wait for the first, the marker makes later calls free.
# setup.sh until 2026-11-04, when the browser moved onto the workbench (its
# setup.sh took the name). The agent never runs this: the server calls
# browser.py with typed arguments, and the user's live view reaches the VNC
# server only through relay.py on the provider's exec API.
set -e
dir="$HOME/.consens/browser"
# -2 since 2026-11-02: the screen is TigerVNC's X server (display.sh). A VM
# set up before keeps its Chrome and only adds that (6 s on a test Sprite).
marker="$dir/setup-done-2"
[ -f "$marker" ] && exit 0
mkdir -p "$dir"
exec 9>"$dir/setup.lock"
flock 9
[ -f "$marker" ] && exit 0
export DEBIAN_FRONTEND=noninteractive
# A VM set up before has a working browser that waits for this: apt waits
# for another apt instead of failing, an install a sleep cut off is finished
# first, and an update that fails for one source (Google's, which Chrome's
# package added) still counts for the others.
apt="sudo apt-get -o DPkg::Lock::Timeout=60"
if ! command -v google-chrome >/dev/null || ! command -v Xtigervnc >/dev/null || ! command -v openbox >/dev/null; then
  sudo dpkg --configure -a || true
  $apt update -qq || true
fi
if ! command -v google-chrome >/dev/null; then
  # In a folder only this user opens.
  download="$(mktemp -d)"
  curl -fsSL --retry 3 -o "$download/chrome.deb" \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  $apt install -y -qq "$download/chrome.deb"
  rm -rf "$download"
fi
if ! command -v openbox >/dev/null; then
  $apt install -y -qq openbox fonts-noto-core fonts-noto-color-emoji
fi
if ! command -v Xtigervnc >/dev/null; then
  $apt install -y -qq --no-install-recommends tigervnc-standalone-server
fi
python3 -c "import playwright" 2>/dev/null || pip3 install -q --disable-pip-version-check playwright==1.64.1
# Chrome's policy (no passwords, cards or addresses; since 2026-10-30 also
# the safety rules) is harden.sh's, which display.sh runs before every start
# of Chrome when it changed.
touch "$marker"
