import os
from typing import Any


class WindowsAdapter:
    os_name = "Windows"

    # Critical Windows processes that must never be terminated by remediation
    PROTECTED_PROCESS_NAMES: frozenset[str] = frozenset(
        {
            "system",
            "system idle process",
            "registry",
            "smss.exe",
            "csrss.exe",
            "wininit.exe",
            "services.exe",
            "lsass.exe",
            "lsm.exe",
            "winlogon.exe",
            "svchost.exe",
            "explorer.exe",
            "dwm.exe",
            "memory compression",
            "ntoskrnl.exe",
            "fontdrvhost.exe",
            "sihost.exe",
            "taskhostw.exe",
        }
    )

    IGNORED_PIDS: frozenset[int] = frozenset({0, 4})

    def get_primary_disk_path(self) -> str:
        system_drive = os.environ.get("SystemDrive", "C:")
        return f"{system_drive}\\"

    def should_include_partition(self, partition: Any) -> bool:
        # Skip CD-ROM drives and unformatted/unready partitions
        if "cdrom" in partition.opts.lower() or not partition.fstype:
            return False
        return True

    def should_skip_process(self, pid: int, name: str) -> bool:
        return pid in self.IGNORED_PIDS or name.lower() == "system idle process"

    def is_protected_process(self, pid: int, name: str) -> bool:
        if pid in self.IGNORED_PIDS:
            return True
        return name.lower() in self.PROTECTED_PROCESS_NAMES