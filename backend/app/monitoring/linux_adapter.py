from typing import Any


class LinuxAdapter:
    os_name = "Linux"

    # Critical Linux/Ubuntu processes that must never be terminated by remediation
    PROTECTED_PROCESS_NAMES: frozenset[str] = frozenset(
        {
            "systemd",
            "init",
            "kthreadd",
            "sshd",
            "dbus-daemon",
            "systemd-journald",
            "systemd-udevd",
            "systemd-logind",
            "systemd-resolved",
            "networkmanager",
            "cron",
            "rsyslogd",
            "dockerd",
            "containerd",
            "gdm3",
            "xorg",
            "wayland",
        }
    )

    IGNORED_FSTYPES: frozenset[str] = frozenset(
        {
            "squashfs",
            "tmpfs",
            "devtmpfs",
            "overlay",
            "proc",
            "sysfs",
            "cgroup",
            "cgroup2",
            "autofs",
        }
    )

    def get_primary_disk_path(self) -> str:
        return "/"

    def should_include_partition(self, partition: Any) -> bool:
        if not partition.fstype or partition.fstype.lower() in self.IGNORED_FSTYPES:
            return False
        # Skip Ubuntu snap loop mounts
        if partition.mountpoint.startswith("/snap/"):
            return False
        return True

    def should_skip_process(self, pid: int, name: str) -> bool:
        return False

    def is_protected_process(self, pid: int, name: str) -> bool:
        # PID 1 is always init/systemd; kernel threads often have low PIDs
        if pid <= 2:
            return True
        return name.lower() in self.PROTECTED_PROCESS_NAMES