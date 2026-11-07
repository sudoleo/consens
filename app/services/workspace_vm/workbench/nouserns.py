"""consens.io workbench: the agent's commands make no user namespaces
(agent-run; docs/agent-mode.md "Ein Rechner").

The browser with every sign-in of the user runs on this computer as the
provider's user; between it and the agent stands the kernel, which keeps the
two users apart. A user namespace lets an ordinary user be root inside it and
reach parts of the kernel that otherwise only root reaches (nf_tables and
the like), and most of the kernel's flaws that made an ordinary user root
went that way (CVE-2024-1086 among them). Ubuntu forbids them by default
since 23.10; the Sprite allows them (``unshare --user --map-root-user``
worked for the agent, test Sprite 2026-10-28).

So agent-run puts every command under this seccomp filter before it becomes
the agent's user: clone and unshare with CLONE_NEWUSER and every setns fail
with EPERM, clone3 with ENOSYS (its flags lie behind a pointer the filter
cannot read; glibc then takes clone, as under Docker's default profile). The
filter holds for the command and everything it starts, and no process under
it can lift it. What it costs: a Chrome the agent starts itself has no
sandbox of its own and needs --no-sandbox (Playwright starts Chromium so
anyway); rootless containers and bubblewrap do not run.

    nouserns.py <program> [args...]

Sets no_new_privs (a filter needs it without CAP_SYS_ADMIN; agent-run sets
it anyway), installs the filter and execs the program. Standard library
only; exit 125 when the filter cannot be installed, so nothing ran.
"""
import ctypes
import os
import struct
import sys

PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2

AUDIT_ARCH_X86_64 = 0xC000003E
AUDIT_ARCH_I386 = 0x40000003
X32_SYSCALL_BIT = 0x40000000
CLONE_NEWUSER = 0x10000000

RET_ALLOW = 0x7FFF0000
RET_ERRNO = 0x00050000
EPERM = 1
ENOSYS = 38

# The system calls by architecture: clone, unshare, setns, clone3.
CALLS = {AUDIT_ARCH_X86_64: {"clone": 56, "unshare": 272, "setns": 308, "clone3": 435},
         AUDIT_ARCH_I386: {"clone": 120, "unshare": 310, "setns": 346, "clone3": 435}}

# struct seccomp_data: nr at 0, arch at 4, args[0]'s low half at 16
# (little endian: x86 only, as CALLS).
NR, ARCH, ARG0_LOW = 0, 4, 16

LD_ABS = 0x20  # BPF_LD | BPF_W | BPF_ABS
JEQ = 0x15     # BPF_JMP | BPF_JEQ | BPF_K
JGE = 0x35     # BPF_JMP | BPF_JGE | BPF_K
JSET = 0x45    # BPF_JMP | BPF_JSET | BPF_K
RET = 0x06     # BPF_RET | BPF_K


def program():
    """The filter as (code, jump if true, jump if false, k), its jumps to
    labels resolved into the classic BPF's relative offsets."""
    lines = [("ld", ARCH),
             ("jeq", AUDIT_ARCH_X86_64, "x86_64", None),
             ("jeq", AUDIT_ARCH_I386, "i386", None),
             ("ret", RET_ALLOW),
             ("label", "x86_64"),
             ("ld", NR),
             # x32's numbers: no program here uses them, none gets past.
             ("jge", X32_SYSCALL_BIT, "deny", None)]
    for arch in ("x86_64", "i386"):
        calls = CALLS[AUDIT_ARCH_X86_64 if arch == "x86_64" else AUDIT_ARCH_I386]
        if arch == "i386":
            lines += [("label", "i386"), ("ld", NR)]
        lines += [("jeq", calls["clone3"], "nosys", None),
                  ("jeq", calls["setns"], "deny", None),
                  ("jeq", calls["clone"], "flags", None),
                  ("jeq", calls["unshare"], "flags", None),
                  ("ret", RET_ALLOW)]
    lines += [("label", "flags"),
              ("ld", ARG0_LOW),
              ("jset", CLONE_NEWUSER, "deny", None),
              ("ret", RET_ALLOW),
              ("label", "deny"),
              ("ret", RET_ERRNO | EPERM),
              ("label", "nosys"),
              ("ret", RET_ERRNO | ENOSYS)]
    labels, count = {}, 0
    for line in lines:
        if line[0] == "label":
            labels[line[1]] = count
        else:
            count += 1
    out = []
    for line in lines:
        kind = line[0]
        if kind == "label":
            continue
        here = len(out)
        if kind == "ld":
            out.append((LD_ABS, 0, 0, line[1]))
        elif kind == "ret":
            out.append((RET, 0, 0, line[1]))
        else:
            code = {"jeq": JEQ, "jge": JGE, "jset": JSET}[kind]
            true = labels[line[2]] - here - 1
            false = 0 if line[3] is None else labels[line[3]] - here - 1
            if not (0 <= true < 256 and 0 <= false < 256):
                raise ValueError("jump out of range")
            out.append((code, true, false, line[1]))
    return out


def install():
    filters = program()
    raw = b"".join(struct.pack("HBBI", *line) for line in filters)
    buffer = ctypes.create_string_buffer(raw, len(raw))

    class Fprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    fprog = Fprog(len(filters), ctypes.cast(buffer, ctypes.c_void_p))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, None, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "no_new_privs")
    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(fprog), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "seccomp")


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: nouserns.py <program> [args...]\n")
        return 125
    try:
        install()
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"nouserns: the filter could not be installed ({exc})\n")
        return 125
    try:
        os.execvp(sys.argv[1], sys.argv[1:])
    except OSError as exc:
        sys.stderr.write(f"nouserns: {sys.argv[1]}: {exc}\n")
        return 127


if __name__ == "__main__":
    sys.exit(main())
