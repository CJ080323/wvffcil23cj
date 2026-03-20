import platform
import shutil
import subprocess


IPTABLES_PATH = shutil.which("iptables")
SUPPORTED = platform.system().lower() == "linux" and bool(IPTABLES_PATH)


def _run_iptables(args):
    if not SUPPORTED:
        return False

    try:
        subprocess.run(
            [IPTABLES_PATH, *args],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


def allow_user(ip):
    return _run_iptables(["-I", "FORWARD", "-s", ip, "-j", "ACCEPT"])


def block_user(ip):
    return _run_iptables(["-D", "FORWARD", "-s", ip, "-j", "ACCEPT"])


def block_all():
    return _run_iptables(["-P", "FORWARD", "DROP"])
