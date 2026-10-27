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

# The browser that ran here before 2026-10-27 and its live view's gateway.
pkill -KILL -f '/opt/google/chrome/' 2>/dev/null || true
pkill -KILL -x Xvfb 2>/dev/null || true
pkill -KILL -x x11vnc 2>/dev/null || true
pkill -KILL -x openbox 2>/dev/null || true
pkill -KILL -f "$legacy/.consens/workspace/gateway.py" 2>/dev/null || true
rm -rf "$legacy/.consens/browser" "$legacy/.local/bin/browser"
for old in browser.py display.sh gateway.py ref-count setup-done-2 setup.lock pause.lock; do
  rm -f "$legacy/.consens/workspace/$old"
done
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

as_user() { setpriv --reuid="$user" --regid="$user" --init-groups --no-new-privs -- env -i HOME="$home" "$@"; }
as_user mkdir -p "$home/chats" "$home/.local/bin" "$home/.config"
exit 0
