#!/bin/bash
# consens.io workspace: installs the browser, its screen and the VNC server
# once (agent_workspace.py). Called by browser.py and gateway.py; the lock
# makes a second caller wait for the first, the marker makes later calls free.
set -e
dir="$HOME/.consens/workspace"
marker="$dir/setup-done-2"
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
# Chrome keeps no passwords, cards or addresses here: the agent can read
# every file of the VM, and sign-ins stay what the user typed in the view.
sudo mkdir -p /etc/opt/chrome/policies/managed
echo '{"PasswordManagerEnabled": false, "AutofillCreditCardEnabled": false, "AutofillAddressEnabled": false,
 "BrowserSignin": 0, "SyncDisabled": true, "MetricsReportingEnabled": false, "PromotionsEnabled": false}' \
  | sudo tee /etc/opt/chrome/policies/managed/consens.json >/dev/null
touch "$marker"
