"""consens.io workspace: whether the screen's abstract X socket is this
user's (display.sh x_ours, since 2026-11-04; docs/agent-mode.md "Ein Rechner").

X clients (Chrome) try the abstract socket @/tmp/.X11-unix/X1 first, and
any user of the computer may bind an abstract name: one the agent's user
held would get Chrome's windows and the user's keys. So Chrome starts only
while every stream socket bound to that name (listening, or bound and not
yet listening) belongs to the user who runs this, and there is one.

The kernel says whose a socket is (sock_diag, UNIX_DIAG_UID: the user that
made it), to every user. Until this the check looked for the socket among
the X server's own descriptors, but Ubuntu 26.04's Xtigervnc is not
dumpable: its /proc/<pid>/fd belongs to root, and the Sprite's root lacks
CAP_SYS_PTRACE, so the check failed on every start and no Chrome ever ran
(test Sprite 2026-11-04). Connections count for nothing: an accepted one
carries the name and the connecting user's uid, and anyone may connect
without the cookie. Other socket types neither: Linux keeps abstract names
apart by type, so the agent's user may bind a datagram socket to the same
name, and Chrome connects to a stream socket only.

    xsocket.py <uid>      exit 0: ours; 1: not ours or none; 2: no answer

Standard library only.
"""
import socket
import struct
import sys

NAME = b"\0/tmp/.X11-unix/X1"
# Linux's values (the module is also read where they differ or are missing).
AF_UNIX, SOCK_STREAM = 1, 1
NETLINK_SOCK_DIAG = 4
SOCK_DIAG_BY_FAMILY = 20
NLM_F_REQUEST, NLM_F_DUMP = 0x1, 0x300
NLMSG_ERROR, NLMSG_DONE = 2, 3
UDIAG_SHOW_NAME, UDIAG_SHOW_UID = 0x01, 0x40
UNIX_DIAG_NAME, UNIX_DIAG_UID = 0, 7
# A bound socket that does not listen yet (it may listen later), and a listening one.
TCP_CLOSE, TCP_LISTEN = 7, 10
HEADER = struct.Struct("=IHHII")
MESSAGE = struct.Struct("=BBBBIII")
ATTRIBUTE = struct.Struct("=HH")


def request(seq=1):
    """The dump of every Unix socket with its name and its user."""
    body = struct.pack("=BBHIII8s", AF_UNIX, 0, 0, 0xFFFFFFFF, 0, UDIAG_SHOW_NAME | UDIAG_SHOW_UID,
                       b"\0" * 8)
    return HEADER.pack(HEADER.size + len(body), SOCK_DIAG_BY_FAMILY, NLM_F_REQUEST | NLM_F_DUMP, seq, 0) + body


def parse(data):
    """The sockets in one answer of the dump, as (type, state, name, uid),
    and whether the dump ended (None: an error)."""
    sockets, offset = [], 0
    while offset + HEADER.size <= len(data):
        length, kind, _, _, _ = HEADER.unpack_from(data, offset)
        if length < HEADER.size or offset + length > len(data):
            return sockets, None
        if kind == NLMSG_DONE:
            return sockets, True
        if kind == NLMSG_ERROR:
            return sockets, None
        if length >= HEADER.size + MESSAGE.size:
            _, kind_of, state, _, _, _, _ = MESSAGE.unpack_from(data, offset + HEADER.size)
            name = uid = None
            at, end = offset + HEADER.size + MESSAGE.size, offset + length
            while at + ATTRIBUTE.size <= end:
                size, which = ATTRIBUTE.unpack_from(data, at)
                if size < ATTRIBUTE.size or at + size > end:
                    break
                payload = data[at + ATTRIBUTE.size:at + size]
                if which == UNIX_DIAG_NAME:
                    name = payload
                elif which == UNIX_DIAG_UID and len(payload) >= 4:
                    uid = struct.unpack("=I", payload[:4])[0]
                at += (size + 3) & ~3
            sockets.append((kind_of, state, name, uid))
        offset += (length + 3) & ~3
    return sockets, False


def ours(sockets, uid):
    """Whether there is a stream socket bound to NAME and every one is uid's."""
    held = [owner for kind, state, name, owner in sockets
            if kind == SOCK_STREAM and state in (TCP_CLOSE, TCP_LISTEN) and name == NAME]
    return bool(held) and all(owner == uid for owner in held)


def dump():
    with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_SOCK_DIAG) as diag:
        diag.settimeout(5)
        diag.sendto(request(), (0, 0))
        sockets = []
        while True:
            found, done = parse(diag.recv(1 << 20))
            sockets.extend(found)
            if done is None:
                raise OSError("sock_diag refused the dump")
            if done:
                return sockets


def main(argv):
    if len(argv) != 2 or not argv[1].isdigit():
        sys.stderr.write("usage: xsocket.py <uid>\n")
        return 2
    try:
        sockets = dump()
    except OSError as exc:
        sys.stderr.write(f"xsocket: {exc}\n")
        return 2
    return 0 if ours(sockets, int(argv[1])) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
