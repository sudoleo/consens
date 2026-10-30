#!/bin/bash
# consens.io browser VM: the rules that hold whoever steers Chrome, the agent
# through browser.py or the user in the live view (since 2026-10-30, the
# server's safety rules, workspace_guard.py). display.sh runs this before it
# starts Chrome and starts none when it fails; it does the work again only
# when the rules of this folder changed (the marker holds their version,
# which display.sh also gives Chrome's restart).
#
# - policy.json is Chrome's managed policy: Google's SafeSites filter (no
#   adult sites), Safe Browsing's warnings without "proceed anyway", SafeSearch,
#   no file dialogs, no extensions, no incognito or guest window, a history
#   nobody deletes, no printing, and neither the VM's files, DevTools, a few
#   of Chrome's own pages nor its debugging port as a page. Chrome runs as
#   the provider's user, who has sudo: a "Save as" over one of the server's
#   scripts, or DevTools on the debugging port, was a way out of the browser
#   into a root shell in the live view. Measured on a test Sprite
#   2026-10-30: DeveloperToolsAvailability 2 also shuts Playwright out of
#   every page (new_page fails), so DevTools stay closed through
#   URLBlocklist (devtools://), which leaves the debugging port to
#   browser.py; DNS over HTTPS (Cloudflare's family resolver) does not
#   work at all, the provider's network rules only let through addresses
#   its own resolver gave out (ERR_CONNECTION_REFUSED).
# - xdg-open opens nothing: Chrome opens a download or another app's link
#   with it, and a downloaded script or .desktop file would run.
# - openbox shows no menu and starts no program (openbox-rc.xml).
set -e
here="$(cd "$(dirname "$0")" && pwd)"
dir="$HOME/.consens/browser"
policy=/etc/opt/chrome/policies/managed/consens.json
mkdir -p "$dir"
version="$(cat "$here/policy.json" "$here/openbox-rc.xml" "$here/openbox-menu.xml" "$here/harden.sh" \
  | sha256sum | cut -c1-16)"
marker="$dir/hardened"
# Done when the marker says so and the policy and xdg-open are as written.
if [ "$(cat "$marker" 2>/dev/null)" = "$version" ] && cmp -s "$here/policy.json" "$policy" \
  && grep -q "consens.io browser VM" /usr/bin/xdg-open 2>/dev/null; then
  exit 0
fi
sudo -n install -D -m 644 "$here/policy.json" "$policy"
# The package's own xdg-open moves aside once (dpkg-divert keeps an update
# from bringing it back); in its place one that opens nothing.
stub='#!/bin/sh
# consens.io browser VM (harden.sh): opens nothing.
exit 1'
if [ -e /usr/bin/xdg-open ] && ! grep -q "consens.io browser VM" /usr/bin/xdg-open; then
  sudo -n dpkg-divert --quiet --local --rename --divert /usr/bin/xdg-open.consens --add /usr/bin/xdg-open
fi
printf '%s\n' "$stub" | sudo -n tee /usr/bin/xdg-open >/dev/null
sudo -n chmod 755 /usr/bin/xdg-open
mkdir -p "$HOME/.config/openbox"
install -m 644 "$here/openbox-rc.xml" "$HOME/.config/openbox/rc.xml"
install -m 644 "$here/openbox-menu.xml" "$HOME/.config/openbox/menu.xml"
# A running openbox takes the new configuration at once.
if pgrep -x openbox >/dev/null; then
  DISPLAY=:1 openbox --reconfigure >/dev/null 2>&1 || true
fi
echo "$version" >"$marker"
