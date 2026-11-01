#!/bin/bash
# consens.io office converter (agent_office.py): the layout of this version,
# run as root by the provider's user whenever its VERSION changed. One VM of
# the operator's for every account, instead of LibreOffice on each workbench.
# - LibreOffice without a screen (Impress, Writer, Calc) with the fonts Office
#   files name (Carlito for Calibri, Caladea for Cambria, Liberation for
#   Arial and Times), poppler-utils for the pages and Pillow for their
#   overview;
# - the user `office`, who converts: no sudo, no home, no shell;
# - convert.sh and sheet.py where only root writes; the version last, once
#   all of it stands.
#   setup.sh <version>
set -eu
version=$1
export DEBIAN_FRONTEND=noninteractive
apt_get() { apt-get -o DPkg::Lock::Timeout=60 -o Dpkg::Options::=--force-confold -y -qq "$@"; }

if ! id -u office >/dev/null 2>&1; then
  useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin office
fi
gpasswd -d office sudo >/dev/null 2>&1 || true
rm -f /etc/sudoers.d/office

apt_get update >/dev/null
apt_get install --no-install-recommends libreoffice-impress libreoffice-writer libreoffice-calc \
  fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation fonts-dejavu-core \
  poppler-utils python3-pil >/dev/null

here=$(dirname -- "$0")
install -D -m 0755 "$here/convert.sh" /usr/local/lib/consens/office/convert.sh
install -D -m 0644 "$here/sheet.py" /usr/local/lib/consens/office/sheet.py
printf '%s\n' "$version" > /usr/local/lib/consens/office/VERSION
