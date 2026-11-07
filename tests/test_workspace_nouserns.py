"""The workbench's seccomp filter against user namespaces
(workspace_vm/workbench/nouserns.py, docs/agent-mode.md
"Ein Rechner"): the filter's program run through a small classic-BPF
interpreter on every platform, and on Linux installed for real in a child
process (the CI runs there)."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "workspace_vm" / "workbench" / "nouserns.py"
spec = importlib.util.spec_from_file_location("workspace_nouserns", PATH)
nouserns = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nouserns)

X86_64 = nouserns.AUDIT_ARCH_X86_64
I386 = nouserns.AUDIT_ARCH_I386
ALLOW = nouserns.RET_ALLOW
EPERM = nouserns.RET_ERRNO | nouserns.EPERM
ENOSYS = nouserns.RET_ERRNO | nouserns.ENOSYS
NEWUSER = nouserns.CLONE_NEWUSER
# clone's flags of a thread (glibc's pthread_create) and of a fork.
THREAD = 0x003D0F00
FORK = 0x01200011


def run(nr, arch=X86_64, arg0=0):
    """The filter's answer to one system call, by the kernel's rules for
    the classic BPF it runs (accumulator, absolute loads, relative jumps)."""
    data = {nouserns.NR: nr, nouserns.ARCH: arch, nouserns.ARG0_LOW: arg0 & 0xFFFFFFFF}
    program = nouserns.program()
    pc, acc = 0, 0
    for _ in range(len(program) + 1):
        code, true, false, k = program[pc]
        if code == nouserns.LD_ABS:
            acc = data[k]
        elif code == nouserns.RET:
            return k
        else:
            taken = {nouserns.JEQ: acc == k, nouserns.JGE: acc >= k, nouserns.JSET: bool(acc & k)}[code]
            pc += true if taken else false
        pc += 1
    raise AssertionError("the program did not end")


def test_user_namespaces_are_refused_and_everything_else_runs():
    calls = nouserns.CALLS[X86_64]
    # No new user namespace, by clone or unshare, and no way into another.
    assert run(calls["clone"], arg0=NEWUSER | 0x11) == EPERM
    assert run(calls["unshare"], arg0=NEWUSER) == EPERM
    assert run(calls["unshare"], arg0=NEWUSER | 0x00020000) == EPERM
    assert run(calls["setns"], arg0=3) == EPERM
    # clone3's flags lie behind a pointer: glibc falls back to clone.
    assert run(calls["clone3"]) == ENOSYS
    # Threads, forks and the other unshares run as before.
    assert run(calls["clone"], arg0=THREAD) == ALLOW
    assert run(calls["clone"], arg0=FORK) == ALLOW
    assert run(calls["unshare"], arg0=0x00000200) == ALLOW
    for nr in (0, 1, 2, 57, 59, 231):
        assert run(nr) == ALLOW
    # The upper half of clone's flags is not CLONE_NEWUSER's.
    assert run(calls["clone"], arg0=1 << 40) == ALLOW


def test_the_32_bit_calls_and_x32_get_no_way_around_it():
    calls = nouserns.CALLS[I386]
    assert run(calls["clone"], arch=I386, arg0=NEWUSER) == EPERM
    assert run(calls["unshare"], arch=I386, arg0=NEWUSER) == EPERM
    assert run(calls["setns"], arch=I386) == EPERM
    assert run(calls["clone3"], arch=I386) == ENOSYS
    assert run(calls["clone"], arch=I386, arg0=THREAD) == ALLOW
    # x86_64's unshare number is another call on i386, and the other way round.
    assert run(nouserns.CALLS[X86_64]["unshare"], arch=I386, arg0=NEWUSER) == ALLOW
    # x32's numbers carry a bit of their own: none passes.
    assert run(nouserns.X32_SYSCALL_BIT | 272, arg0=NEWUSER) == EPERM
    assert run(nouserns.X32_SYSCALL_BIT | 1) == EPERM


def test_the_program_fits_the_kernels_format():
    program = nouserns.program()
    assert 0 < len(program) < 4096
    for code, true, false, k in program:
        assert 0 <= true < 256 and 0 <= false < 256 and 0 <= k < 1 << 32
    # Every path ends in a return: the last instruction is one.
    assert program[-1][0] == nouserns.RET


def test_no_program_no_filter():
    """Without a program to run, nothing is installed and nothing runs."""
    result = subprocess.run([sys.executable, str(PATH)], capture_output=True, text=True)
    assert result.returncode == 125 and "usage" in result.stderr


CHECK = r"""
import ctypes, errno, os, subprocess, threading
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
def call(nr, *args):
    ctypes.set_errno(0)
    result = libc.syscall(ctypes.c_long(nr), *[ctypes.c_long(a) for a in args])
    return result, ctypes.get_errno()
assert call(272, 0x10000000) == (-1, errno.EPERM), "unshare"
assert call(308, 0, 0) == (-1, errno.EPERM), "setns"
assert call(435, 0, 0) == (-1, errno.ENOSYS), "clone3"
try:
    os.unshare(os.CLONE_NEWUSER)
except AttributeError:
    pass
except PermissionError:
    pass
else:
    raise AssertionError("os.unshare")
done = []
thread = threading.Thread(target=lambda: done.append(1))
thread.start(); thread.join()
assert done == [1], "thread"
assert subprocess.run(["true"]).returncode == 0, "fork and exec"
print("ok")
"""


@pytest.mark.skipif(sys.platform != "linux" or os.uname().machine != "x86_64",
                    reason="the filter is Linux's, for x86_64 (the Sprite)")
def test_installed_for_real_it_refuses_user_namespaces_and_keeps_threads_and_forks():
    result = subprocess.run([sys.executable, str(PATH), sys.executable, "-I", "-c", CHECK],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
    # unshare(1) fails as the agent's command would see it.
    if any(os.access(os.path.join(folder, "unshare"), os.X_OK) for folder in os.get_exec_path()):
        blocked = subprocess.run([sys.executable, str(PATH), "unshare", "--user", "true"],
                                 capture_output=True, text=True, timeout=60)
        assert blocked.returncode != 0
