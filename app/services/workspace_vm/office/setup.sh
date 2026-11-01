#!/bin/bash
# consens.io office converter (agent_office.py): the layout of this version,
# run as root by the provider's user whenever its VERSION changed. One VM of
# the operator's for every account, instead of LibreOffice on each workbench.
# - LibreOffice without a screen (Impress, Writer, Calc) with the fonts Office
#   files name (Carlito for Calibri, Caladea for Cambria, Liberation for
#   Arial and Times), poppler-utils for the pages and Pillow for their
#   overview;
# - the users office0 to office2, one per place a conversion takes
#   (convert.sh): no sudo, no home, no shell;
# - convert.sh and sheet.py where only root writes; the version last, once
#   all of it stands.
#   setup.sh <version>
set -eu
version=$1
export DEBIAN_FRONTEND=noninteractive
apt_get() { apt-get -o DPkg::Lock::Timeout=60 -o Dpkg::Options::=--force-confold -y -qq "$@"; }

for user in office0 office1 office2; do
  if ! id -u "$user" >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$user"
  fi
  gpasswd -d "$user" sudo >/dev/null 2>&1 || true
  rm -f "/etc/sudoers.d/$user"
done

# An install broken off before (a deploy, a stopped setup) leaves dpkg
# half done, and every later apt-get would refuse until it is finished.
dpkg --configure -a >/dev/null 2>&1 || true
apt_get update >/dev/null
apt_get install --no-install-recommends libreoffice-impress libreoffice-writer libreoffice-calc \
  fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation fonts-dejavu-core \
  poppler-utils python3-pil >/dev/null
# The downloaded packages (~200 MB) would stay on the disk, which Sprites bill.
apt-get clean

here=$(dirname -- "$0")
install -D -m 0755 "$here/convert.sh" /usr/local/lib/consens/office/convert.sh
install -D -m 0644 "$here/sheet.py" /usr/local/lib/consens/office/sheet.py
printf '%s\n' "$version" > /usr/local/lib/consens/office/VERSION
