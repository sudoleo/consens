#!/bin/bash
# consens.io workspace: the layout of this version (agent_workspace.prepare
# runs it as root whenever its VERSION changed; every step may run again).
# - the agent's own user without sudo, its home closed to others, and the
#   provider's home closed to it (the server's files, and since 2026-11-04
#   the browser: Chrome, its screen and its profile with every sign-in run
#   here as the provider's user, docs/agent-mode.md "Ein Rechner");
# - the agent's own /tmp (agent-run binds it over /tmp for each command), so
#   nothing of the agent lies in the way of the screen's sockets and locks;
# - once: what lay in the provider's home before (chats' folders, the notes,
#   repositories) moves to the agent's; once since 2026-11-04 (MERGED):
#   whatever browser, screen or tunnel an older layout left goes, and so do
#   the agent's processes that still share the real /tmp;
# - installs into the user's own folders: pip falls back to them by itself
#   (site-packages is root's), uv tool by default, npm into the project (nvm,
#   which runs Node here, takes no prefix of its own).
set -eu
user=agent
uid=1500
home=/home/agent
legacy=/home/sprite
state=/var/lib/consens
tmp=$state/agent-tmp
merged=$state/one-computer

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
# Packages installed for the agent (vm_install_packages, as root) start no
# service: it would run as root, outside the agent's commands and their
# limits. invoke-rc.d and deb-systemd-invoke ask this first; 101 refuses.
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d

# The agent's /tmp: root's folder above it, so the agent cannot swap it.
install -d -o root -g root -m 0755 "$state"
install -d -o "$user" -g "$user" -m 1777 "$tmp"

# Once per computer since 2026-11-04 (the marker lies on its disk, so a
# restore to a checkpoint from before does it again): the browser that ran
# here before 2026-10-27 with its profile and screen, the live view's
# gateway, the localhost tunnel of the two-VM layout (2026-10-29 to
# 2026-11-04) and the leftovers of the provider's user in /tmp. The agent's
# processes end once too: they share the real /tmp, where the browser's
# screen keeps its sockets from now on. Chrome, its screen and its profile
# start anew under display.sh; the account's sign-ins are made again.
if [ ! -e "$merged" ]; then
  pkill -KILL -u sprite -f '/opt/google/chrome/|google-chrome|cdp\.py' 2>/dev/null || true
  pkill -KILL -u sprite -x Xvfb 2>/dev/null || true
  pkill -KILL -u sprite -x x11vnc 2>/dev/null || true
  pkill -KILL -u sprite -x Xtigervnc 2>/dev/null || true
  pkill -KILL -u sprite -x openbox 2>/dev/null || true
  pkill -KILL -f "$legacy/.consens/workspace/gateway.py" 2>/dev/null || true
  pkill -KILL -f "tunnel\.py (listen|connect)" 2>/dev/null || true
  pkill -KILL -u "$user" 2>/dev/null || true
  rm -rf "$legacy/.consens/browser" "$legacy/.local/bin/browser" /usr/local/lib/consens/tunnel.py
  find /tmp -maxdepth 1 -user sprite \( -name 'playwright*' -o -name '.com.google.Chrome.*' \
    -o -name 'com.google.Chrome.*' \) -exec rm -rf {} + 2>/dev/null || true
  for old in gateway.py ref-count setup-done-2 setup.lock pause.lock tunnel.py; do
    rm -f "$legacy/.consens/workspace/$old"
  done
  touch "$merged"
fi
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

# Tools every workspace has: ripgrep and poppler-utils (pdftotext and the
# like, for the PDFs the agent reads) from the Ubuntu mirrors, and Chrome,
# Google's package. The browser the user shares with the agent runs it as
# the provider's user (display.sh, with its screen and Playwright from
# install.sh); the agent runs it headless for checks the user need not see,
# such as its dev server or a page it serves on localhost (screenshots,
# PDFs; no sign-ins, its own profile). Chrome's policy holds for every
# user of the computer since 2026-11-04 (harden.sh): no file:// pages,
# printing off, which leaves headless --print-to-pdf and Playwright's pdf()
# working (measured with Chrome 153 and the policy, review 2026-11-04).
# `google-chrome --headless=new` runs as the agent's user with its sandbox
# on: no_new_privs ignores the setuid helper, but the VM
# allows user namespaces (test Sprite 2026-10-28), so no --no-sandbox and no
# wrapper. Workspaces from before 2026-10-27 have Xvfb and x11vnc of the
# old screen: those go (TigerVNC's X server took their place on
# 2026-11-02). A failed install costs the workspace that tool until the
# next version, never its user (the steps above).
export DEBIAN_FRONTEND=noninteractive
apt_get() { apt-get -o DPkg::Lock::Timeout=60 -o Dpkg::Options::=--force-confold -y -qq "$@"; }
installed() { [ "$(dpkg-query -W -f='${Status}' "$1" 2>/dev/null)" = "install ok installed" ]; }
# Chrome's package adds Google's apt source, and a daily job of it adds the
# source again: until 2026-11-04 the workbench reached no Google server, and
# every apt run warned "Failed to fetch dl.google.com" (2026-10-28). It stays
# off, so an apt run for the agent (vm_install_packages) never updates the
# browser's Chrome under it. The package reads /etc/default/google-chrome
# before it adds anything.
no_chrome_source() {
  printf 'repo_add_once="false"\nrepo_reenable_on_distupgrade="false"\n' > /etc/default/google-chrome
  rm -f /etc/apt/sources.list.d/google-chrome.list /etc/apt/sources.list.d/google-chrome.sources
}
tools() {
  local old="" package
  no_chrome_source
  for package in xvfb x11vnc; do
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
    # In a folder only root can open: the package root installs is never
    # one the agent's user put there.
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
