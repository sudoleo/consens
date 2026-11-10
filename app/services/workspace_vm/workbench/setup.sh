#!/bin/bash
# consens.io workspace: the layout of this version (agent_workspace.prepare
# runs it as root whenever its VERSION changed; every step may run again).
# - the agent's own user without sudo, its home closed to others, and the
#   provider's home closed to it (the server's files, and the browser:
#   Chrome, its screen and its profile with every sign-in run here as the
#   provider's user, docs/agent-mode.md "Ein Rechner");
# - the agent's own /tmp (agent-run binds it over /tmp for each command), so
#   nothing of the agent lies in the way of the screen's sockets and locks;
# - once: what lay in the provider's home before (chats' folders, the notes,
#   repositories) moves to the agent's; once per computer ($merged):
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

# The agent's /tmp: root's folder above it, so the agent cannot swap it.
install -d -o root -g root -m 0755 "$state"
install -d -o "$user" -g "$user" -m 1777 "$tmp"

# Once per computer (the marker lies on its disk, so a restore to a
# checkpoint from before does it again): what older layouts left, the
# browser with its profile and screen, the live view's gateway, the
# localhost tunnel of the two-VM layout and the leftovers of the provider's
# user in /tmp. The agent's processes end once too: they share the real
# /tmp, where the browser's screen keeps its sockets. Chrome, its screen
# and its profile start anew under display.sh; the account's sign-ins are
# made again.
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
# An older layout froze the agent's processes while the user had the
# browser (pause.py); one still frozen goes on, and the pause goes.
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

# The runtimes there that hand a command to pyenv (python, pip, poetry and
# the like) call its shims by their full path, so pyenv never learns of
# /.sprite/bin. Where a project's .python-version names a version that is
# not installed, pyenv looks for the system's command on PATH without its
# own shims, finds the runtime in /.sprite/bin again and calls itself until
# the command's time limit: every python command in such a repository hung.
# pyenv leaves the folders in _PYENV_SHIM_PATHS_<NAME> out of that look:
# then the system's python3 answers, or pyenv says at once that the version
# is not installed. In every login shell, the agent's and the user's terminal.
runtimes=/.sprite/bin
for shim in "$runtimes"/*; do
  grep -qs 'PYENV_ROOT/shims' "$shim" || continue
  name=$(basename -- "$shim" | tr 'a-z-' 'A-Z_' | sed 's/[^A-Z0-9_]/_/g')
  printf 'export _PYENV_SHIM_PATHS_%s=%s\n' "$name" "$runtimes"
done > /etc/profile.d/consens-pyenv.sh
chmod 644 /etc/profile.d/consens-pyenv.sh

# pyenv rehashes its shims after every `pip install` (its exec hook
# pip-rehash) and stops where it cannot write them. They are root's, so for
# the agent's user every installation that had worked ended with "pyenv:
# cannot rehash" and exit 1, and `pip install x && python3 …` never reached
# its second half (test Sprite 2026-11-10). pyenv reads hooks in
# /etc/pyenv.d after its own: this one hands the command back to pip itself
# where the rehash could only fail. The agent needs no shim: pip puts its
# commands in ~/.local/bin, which is on its PATH.
install -d -m 0755 /etc/pyenv.d/exec
cat > /etc/pyenv.d/exec/consens-rehash.bash <<'HOOK'
if [ -n "${PYENV_REHASH_REAL_COMMAND:-}" ] && [ ! -w "${PYENV_ROOT}/shims" ]; then
  PYENV_COMMAND_PATH="$(pyenv-which "$PYENV_COMMAND")"
  PYENV_BIN_PATH="${PYENV_COMMAND_PATH%/*}"
  unset PYENV_REHASH_REAL_COMMAND
fi
HOOK
chmod 644 /etc/pyenv.d/exec/consens-rehash.bash

# Tools every workspace has: ripgrep and poppler-utils (pdftotext and the
# like, for the PDFs the agent reads) from the Ubuntu mirrors, and Chrome,
# Google's package. The browser the user shares with the agent runs it as
# the provider's user (display.sh, with its screen and Playwright from
# install.sh); the agent runs it headless for checks the user need not see,
# such as its dev server or a page it serves on localhost (screenshots,
# PDFs; no sign-ins, its own profile). Chrome's policy holds for every
# user of the computer (harden.sh): no file:// pages, printing off, which
# leaves headless --print-to-pdf and Playwright's pdf() working (measured
# with Chrome 153 and the policy). `google-chrome --headless=new` runs as
# the agent's user with --no-sandbox: no_new_privs ignores the setuid
# helper, and agent-run's filter (nouserns.py) leaves it no user namespace,
# which kept the agent's user from root's parts of the kernel more than the
# sandbox kept a page from the agent's own files (its commands reach them
# anyway). Older workspaces have Xvfb and x11vnc of the old screen: those
# go (TigerVNC's X server took their place). A failed install costs the
# workspace that tool until the next version, never its user (the steps
# above).
export DEBIAN_FRONTEND=noninteractive
apt_get() { apt-get -o DPkg::Lock::Timeout=60 -o Dpkg::Options::=--force-confold -y -qq "$@"; }
installed() { [ "$(dpkg-query -W -f='${Status}' "$1" 2>/dev/null)" = "install ok installed" ]; }
# Chrome's package adds Google's apt source, and a daily job of it adds the
# source again. It stays off, so an apt run for the agent
# (vm_install_packages) never updates the browser's Chrome under it. The
# package reads /etc/default/google-chrome before it adds anything.
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
