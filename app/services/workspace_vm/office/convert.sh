#!/bin/bash
# consens.io office converter: one Office file on stdin; on stdout a tar with
# its PDF (in.pdf), an overview of its first pages (pages.png) and their
# count (pages.txt) (agent_office.render). Run as root by the provider's
# user. LibreOffice and its helpers run as the user `office` in a folder of
# this conversion alone; afterwards every process and file of that user
# goes, so a file never meets another account's.
#   convert.sh <extension> <seconds> <overview pages>
# Exit 2: a type it does not take, 3: LibreOffice made no PDF of the file.
set -u
ext=$1
seconds=$2
shown=$3
case "$ext" in
  pptx|ppt|odp|docx|doc|odt|rtf|xlsx|xls|ods) ;;
  *) echo "Not an Office file this converter takes: .$ext" >&2; exit 2 ;;
esac
dir=$(mktemp -d /tmp/office.XXXXXXXXXX) || exit 1
cleanup() {
  pkill -KILL -u office 2>/dev/null
  rm -rf -- "$dir"
  find /tmp /var/tmp /dev/shm -xdev -user office -exec rm -rf -- {} + 2>/dev/null
}
trap cleanup EXIT
chown office:office "$dir"
chmod 700 "$dir"
as_office() {
  setpriv --reuid=office --regid=office --init-groups --no-new-privs -- \
    env -i HOME="$dir" PATH=/usr/bin:/bin LANG=C.UTF-8 "$@"
}

as_office sh -c 'cat > "$1"' sh "$dir/in.$ext" || exit 1
as_office timeout --kill-after=5 "$seconds" soffice --headless --norestore --nolockcheck \
  "-env:UserInstallation=file://$dir/profile" --convert-to pdf --outdir "$dir" "$dir/in.$ext" >/dev/null 2>&1
if [ ! -s "$dir/in.pdf" ]; then
  echo "LibreOffice could not turn the file into a PDF (damaged, protected or not what its name says)." >&2
  exit 3
fi
as_office timeout 30 pdfinfo "$dir/in.pdf" 2>/dev/null | sed -n 's/^Pages:[[:space:]]*//p' > "$dir/pages.txt"
as_office timeout 60 pdftoppm -r 40 -png -l "$shown" "$dir/in.pdf" "$dir/page" >/dev/null 2>&1 || exit 1
as_office timeout 30 /usr/bin/python3 /usr/local/lib/consens/office/sheet.py "$dir" || exit 1
tar -C "$dir" -cf - in.pdf pages.png pages.txt
