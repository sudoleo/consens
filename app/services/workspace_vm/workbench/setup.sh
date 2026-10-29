#!/bin/bash
# consens.io workbench: the layout of this version (agent_workspace.prepare
# runs it as root whenever its VERSION changed; every step may run again).
# - the agent's own user without sudo, its home closed to others, and the
#   provider's home closed to it (this folder, the server's files);
# - once: what lay in the provider's home before (chats' folders, the notes,
#   repositories) moves to the agent's, and the browser that ran here before
#   2026-10-27 goes, its profile with every sign-in too (it has a VM of its
#   own now);
# - installs into the user's own folders: pip falls back to them by itself
#   (site-packages is root's), uv tool by default, npm into the project (nvm,
#   which runs Node here, takes no prefix of its own).
set -eu
user=agent
uid=1500
home=/home/agent
legacy=/home/sprite

if ! id -u "$user" >/dev/null 2>&1; then
  useradd --create-home --home-dir "$home" --uid "$uid" --user-group --shell /bin/bash "$user"
fi
# Never in the provider's group, never with sudo.
gpasswd -d "$user" sprite >/dev/null 2>&1 || true
gpasswd -d "$user" sudo >/dev/null 2>&1 || true
rm -f "/etc/sudoers.d/$user"
mkdir -p "$home"
chown "$user:$user" "$home"
chmod 700 "$home"
chmod 750 "$legacy"

# The browser that ran here before 2026-10-27 (as the provider's user; the
# agent's headless Chrome goes on) and its live view's gateway.
pkill -KILL -u sprite -f '/opt/google/chrome/' 2>/dev/null || true
pkill -KILL -x Xvfb 2>/dev/null || true
pkill -KILL -x x11vnc 2>/dev/null || true
pkill -KILL -x openbox 2>/dev/null || true
pkill -KILL -f "$legacy/.consens/workspace/gateway.py" 2>/dev/null || true
rm -rf "$legacy/.consens/browser" "$legacy/.local/bin/browser"
# Its leftovers in /tmp (Playwright's and Chrome's folders of the provider's
# user, seen by the agent on 2026-10-28), never the agent's own.
find /tmp -maxdepth 1 -user sprite \( -name 'playwright*' -o -name '.com.google.Chrome.*' \
  -o -name 'com.google.Chrome.*' \) -exec rm -rf {} + 2>/dev/null || true
for old in browser.py display.sh gateway.py ref-count setup-done-2 setup.lock pause.lock; do
  rm -f "$legacy/.consens/workspace/$old"
done
# Until 2026-10-29 a takeover of the browser froze the agent's processes
# (pause.py); one frozen at the change goes on, and the pause goes.
pkill -KILL -f "$legacy/.consens/workspace/pause.py" 2>/dev/null || true
for group in /sys/fs/cgroup/consens-agent /sys/fs/cgroup/consens-user; do
  [ -e "$group/cgroup.freeze" ] && echo 0 > "$group/cgroup.freeze" 2>/dev/null || true
done
pkill -CONT -u "$user" 2>/dev/null || true
rm -f "$legacy/.consens/workspace/pause.py" "$legacy/.consens/workspace/control.json"
# Background processes of the old layout ran as the provider's user.
if [ -d "$legacy/.consens/processes" ] && [ ! -e "$legacy/.consens/processes/.v2" ]; then
  pkill -KILL -u sprite -f "$legacy/.consens/processes/" 2>/dev/null || true
  rm -rf "$legacy/.consens/processes"
fi
mkdir -p "$legacy/.consens/processes"
touch "$legacy/.consens/processes/.v2"

# Once: the agent's files from the provider's home.
move() {
  local from=$1 to=$2
  [ -e "$from" ] || return 0
  if [ ! -e "$to" ]; then
    mv -- "$from" "$to"
  elif [ -d "$from" ] && [ -d "$to" ]; then
    for item in "$from"/* "$from"/.[!.]*; do
      [ -e "$item" ] || continue
      [ -e "$to/$(basename -- "$item")" ] || mv -- "$item" "$to/"
    done
    rm -rf -- "$from"
  fi
  chown -R "$user:$user" -- "$to"
}
move "$legacy/chats" "$home/chats"
move "$legacy/NOTES.md" "$home/NOTES.md"
move "$legacy/repos" "$home/repos"

# The runtimes in /.sprite/bin are shims that write their lines into
# /etc/profile.d/languages_env and languages_paths on first use, and stop
# when they cannot. Those files belong to the provider's user, whose shells
# read them, so the agent's user may never write there: each shim runs once
# as the provider's user here, and later finds its lines.
for shim in /.sprite/bin/*; do
  grep -q 'LANG_ENV=' "$shim" 2>/dev/null || continue
  setpriv --reuid=sprite --regid=sprite --init-groups -- env -i HOME="$legacy" PATH=/usr/bin:/bin \
    timeout 30 "$shim" --version </dev/null >/dev/null 2>&1 &
done
wait

# Tools every workbench has for the agent: ripgrep and poppler-utils
# (pdftotext and the like, for the PDFs it reads) from the Ubuntu mirrors,
# which the policy allows, and headless Chrome for pages on the workbench
# itself, such as the agent's dev server or a local file (screenshots,
# PDFs; no sign-ins: the shared browser with those is a VM of its own).
# `google-chrome --headless=new` runs as the agent's user with its sandbox
# on: no_new_privs ignores the setuid helper, but the VM allows user
# namespaces (test Sprite 2026-10-28), so no --no-sandbox and no wrapper.
# Chrome comes from Google's server, which agent_workspace.prepare opens
# around this script alone. Workbenches from before 2026-10-27 have Chrome
# already, with the old browser's screen, VNC server and window manager:
# those three go, Chrome stays. A failed install costs the workbench that
# tool until the next version, never its user (the steps above).
export DEBIAN_FRONTEND=noninteractive
apt_get() { apt-get -o DPkg::Lock::Timeout=60 -o Dpkg::Options::=--force-confold -y -qq "$@"; }
installed() { [ "$(dpkg-query -W -f='${Status}' "$1" 2>/dev/null)" = "install ok installed" ]; }
# Chrome's package adds Google's apt source, and a daily job of it adds the
# source again: the workbench reaches no Google server, so every apt run of
# the agent warned "Failed to fetch dl.google.com" (2026-10-28). The
# package reads /etc/default/google-chrome before it adds anything.
no_chrome_source() {
  printf 'repo_add_once="false"\nrepo_reenable_on_distupgrade="false"\n' > /etc/default/google-chrome
  rm -f /etc/apt/sources.list.d/google-chrome.list /etc/apt/sources.list.d/google-chrome.sources
}
tools() {
  local old="" package
  no_chrome_source
  for package in xvfb x11vnc openbox; do
    if installed "$package"; then old="$old $package"; fi
  done
  if [ -n "$old" ]; then
    # shellcheck disable=SC2086
    apt_get purge $old >/dev/null || return 1
  fi
  command -v rg >/dev/null 2>&1 && command -v pdftotext >/dev/null 2>&1 \
    && command -v google-chrome >/dev/null 2>&1 && return 0
  apt_get update >/dev/null || return 1
  if ! command -v rg >/dev/null 2>&1 || ! command -v pdftotext >/dev/null 2>&1; then
    apt_get install --no-install-recommends ripgrep poppler-utils >/dev/null || return 1
  fi
  if ! command -v google-chrome >/dev/null 2>&1; then
    # In a folder only root can open: the agent's user shares /tmp and must
    # never swap the package root installs.
    local download status
    download=$(mktemp -d) || return 1
    curl -fsSL --retry 3 -o "$download/chrome.deb" \
      https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
      && apt_get install "$download/chrome.deb" >/dev/null
    status=$?
    rm -rf -- "$download"
    no_chrome_source
    return "$status"
  fi
}
tools || echo "setup: a tool could not be installed (ripgrep, poppler-utils, Chrome)" >&2

as_user() { setpriv --reuid="$user" --regid="$user" --init-groups --no-new-privs -- env -i HOME="$home" "$@"; }
as_user mkdir -p "$home/chats" "$home/.local/bin" "$home/.config"
exit 0
