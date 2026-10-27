#!/bin/bash
# consens.io browser VM: installs the browser, its screen and the VNC server
# once (agent_browser.py). Called by browser.py and relay.py; the lock makes
# a second caller wait for the first, the marker makes later calls free.
# No code of the agent ever runs in this VM: the server calls browser.py with
# typed arguments, and the user's live view reaches the VNC server only
# through relay.py on the provider's exec API.
set -e
dir="$HOME/.consens/browser"
marker="$dir/setup-done-1"
[ -f "$marker" ] && exit 0
mkdir -p "$dir"
exec 9>"$dir/setup.lock"
flock 9
[ -f "$marker" ] && exit 0
export DEBIAN_FRONTEND=noninteractive
if ! command -v google-chrome >/dev/null || ! command -v Xvfb >/dev/null || ! command -v x11vnc >/dev/null; then
  curl -fsSL --retry 3 -o /tmp/consens-chrome.deb \
    https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  sudo apt-get update -qq
  sudo apt-get install -y -qq /tmp/consens-chrome.deb xvfb x11vnc openbox fonts-noto-core fonts-noto-color-emoji
  rm -f /tmp/consens-chrome.deb
fi
python3 -c "import playwright" 2>/dev/null || pip3 install -q --disable-pip-version-check playwright==1.64.1
# Chrome keeps no passwords, cards or addresses: sign-ins stay what the user
# typed in the view, and the agent reads pages only through browser.py,
# which never shows a password field's value.
sudo mkdir -p /etc/opt/chrome/policies/managed
echo '{"PasswordManagerEnabled": false, "AutofillCreditCardEnabled": false, "AutofillAddressEnabled": false,
 "BrowserSignin": 0, "SyncDisabled": true, "MetricsReportingEnabled": false, "PromotionsEnabled": false}' \
  | sudo tee /etc/opt/chrome/policies/managed/consens.json >/dev/null
touch "$marker"
