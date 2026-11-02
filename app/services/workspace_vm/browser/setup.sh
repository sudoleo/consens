#!/bin/bash
# consens.io browser VM: installs the browser, its screen and the VNC server
# once (agent_browser.py). Called by browser.py and relay.py; the lock makes
# a second caller wait for the first, the marker makes later calls free.
# No code of the agent ever runs in this VM: the server calls browser.py with
# typed arguments, and the user's live view reaches the VNC server only
# through relay.py on the provider's exec API.
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
if ! command -v google-chrome >/dev/null || ! command -v Xtigervnc >/dev/null; then
  sudo apt-get update -qq
fi
if ! command -v google-chrome >/dev/null; then
  curl -fsSL --retry 3 -o /tmp/consens-chrome.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  sudo apt-get install -y -qq /tmp/consens-chrome.deb openbox fonts-noto-core fonts-noto-color-emoji
  rm -f /tmp/consens-chrome.deb
fi
if ! command -v Xtigervnc >/dev/null; then
  sudo apt-get install -y -qq --no-install-recommends tigervnc-standalone-server
fi
python3 -c "import playwright" 2>/dev/null || pip3 install -q --disable-pip-version-check playwright==1.64.1
# Chrome's policy (no passwords, cards or addresses; since 2026-10-30 also
# the safety rules) is harden.sh's, which display.sh runs before every start
# of Chrome when it changed.
touch "$marker"
