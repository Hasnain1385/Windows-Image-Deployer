from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List, Dict, Optional, Tuple

# Helper for running commands with logging and robust error handling
class CmdResult:
    def __init__(self, ok: bool, out: str, err: str, code: int):
        self.ok = ok
        self.out = out
        self.err = err
        self.code = code

    def __repr__(self) -> str:
        return f"CmdResult(ok={self.ok}, code={self.code})"


class SystemOps:
    TMP_WIN = "W"  # temporary drive letter for Windows partition
    TMP_ESP = "S"  # temporary drive letter for ESP (GPT)

    @staticmethod
    def run_cmd(cmd: list[str] | str, timeout: Optional[int] = None) -> CmdResult:
        try:
            # Hide child console windows on Windows
            startupinfo = None
            creationflags = 0
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            except Exception:
                startupinfo = None
                creationflags = 0

            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=isinstance(cmd, str),
                timeout=timeout,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            out = p.stdout or ""
            err = p.stderr or ""
            ok = p.returncode == 0
            return CmdResult(ok, out, err, p.returncode)
        except Exception as e:
            return CmdResult(False, "", str(e), -1)

    @staticmethod
    def run_powershell(script: str, timeout: Optional[int] = None) -> CmdResult:
        # Execute PowerShell reliably with arguments list to avoid cmd parsing issues
        args = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden",
            "-Command", script,
        ]
        # Hide child console windows on Windows
        startupinfo = None
        creationflags = 0
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        except Exception:
            startupinfo = None
            creationflags = 0
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, startupinfo=startupinfo, creationflags=creationflags)
        out = p.stdout or ""
        err = p.stderr or ""
        ok = p.returncode == 0
        return CmdResult(ok, out, err, p.returncode)

    # ------------- ISO Mount / WIM path -------------
    @staticmethod
    def mount_iso(iso_path: Path) -> Tuple[bool, str, Optional[str]]:
        # Returns (ok, mount_letter, message)
        ps = (
            "$img = Mount-DiskImage -ImagePath '" + str(iso_path) + "' -PassThru; "
            "$vol = Get-Volume -DiskImage $img | Where-Object {$_.DriveLetter} | Select -First 1; "
            "if ($vol) { $vol.DriveLetter } else { '' }"
        )
        res = SystemOps.run_powershell(ps)
        if not res.ok:
            return False, "", res.err or res.out
        letter = res.out.strip().rstrip(":")
        if not letter:
            return False, "", "Failed to determine ISO drive letter"
        return True, letter + ":\\", None

    @staticmethod
    def unmount_iso(iso_path: Path) -> None:
        ps = "Dismount-DiskImage -ImagePath '" + str(iso_path) + "'"
        SystemOps.run_powershell(ps)

    @staticmethod
    def resolve_wim_from_source(source: Path) -> Tuple[bool, Optional[Path], str, Optional[str]]:
        # Returns (from_iso, wim_path, mount_root, error)
        if source.suffix.lower() == ".wim":
            return False, source, "", None
        if source.suffix.lower() == ".iso":
            ok, mount_root, msg = SystemOps.mount_iso(source)
            if not ok:
                return False, None, "", msg
            wim = Path(mount_root) / "sources" / "install.wim"
            if not wim.exists():
                SystemOps.unmount_iso(source)
                return True, None, mount_root, f"install.wim not found in {wim.parent}"
            return True, wim, mount_root, None
        return False, None, "", "Unsupported source type"

    # ------------- Disk listing -------------
    @staticmethod
    def list_disks() -> List[Dict]:
        # Use PowerShell Get-Disk to enumerate disks
        ps = (
            "Get-Disk | Select Number, FriendlyName, SerialNumber, PartitionStyle, Size, BusType | ConvertTo-Json -Depth 4"
        )
        res = SystemOps.run_powershell(ps)
        if not res.ok:
            raise RuntimeError(res.err or res.out)
        try:
            data = json.loads(res.out)
        except Exception as ex:
            raise RuntimeError(f"Failed to parse disk list: {ex}\n{res.out}")
        if isinstance(data, dict):
            data = [data]
        disks = []
        for d in data:
            size = int(d.get("Size", 0))
            disks.append({
                "Number": int(d.get("Number")),
                "Model": d.get("FriendlyName") or "",
                "Serial": d.get("SerialNumber") or "",
                "Style": d.get("PartitionStyle") or "Unknown",
                "Size": size,
                "SizeGB": round(size / (1024**3), 2),
            })
        return disks

    # ------------- DiskPart scripts -------------
    @staticmethod
    def diskpart(script: str) -> CmdResult:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
            f.write(script)
            path = f.name
        try:
            args = ["diskpart", "/s", path]
            return SystemOps.run_cmd(args)
        finally:
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def prepare_disk_mbr(disk_number: int) -> CmdResult:
        # Create single active NTFS primary, letter W
        s = f"""
select disk {disk_number}
clean
convert mbr
create partition primary
format fs=ntfs quick label=Windows
active
assign letter={SystemOps.TMP_WIN}
list volume
exit
""".strip()
        return SystemOps.diskpart(s)

    @staticmethod
    def prepare_disk_gpt(disk_number: int) -> CmdResult:
        s = f"""
select disk {disk_number}
clean
convert gpt
create partition efi size=100
format quick fs=fat32 label=System
assign letter={SystemOps.TMP_ESP}
create partition msr size=16
create partition primary
format fs=ntfs quick label=Windows
assign letter={SystemOps.TMP_WIN}
list volume
exit
""".strip()
        return SystemOps.diskpart(s)

    @staticmethod
    def cleanup_letters(disk_number: int) -> None:
        s = f"""
select disk {disk_number}
select volume {SystemOps.TMP_WIN}
remove letter={SystemOps.TMP_WIN}
select volume {SystemOps.TMP_ESP}
remove letter={SystemOps.TMP_ESP}
exit
""".strip()
        SystemOps.diskpart(s)

    # ------------- DISM info and apply -------------
    @staticmethod
    def dism_get_wim_info(wim_path: Path) -> Tuple[bool, List[Tuple[int, str]], str]:
        args = ["dism", "/English", "/Get-WimInfo", f"/WimFile:{str(wim_path)}"]
        res = SystemOps.run_cmd(args)
        if not res.ok:
            return False, [], res.err or res.out
        lines = res.out.splitlines()
        entries: List[Tuple[int, str]] = []
        cur_index = None
        cur_name = None
        for ln in lines:
            ln = ln.strip()
            if ln.lower().startswith("index :"):
                try:
                    cur_index = int(ln.split(":", 1)[1].strip())
                except Exception:
                    cur_index = None
            elif ln.lower().startswith("name :"):
                cur_name = ln.split(":", 1)[1].strip()
            if cur_index is not None and cur_name:
                entries.append((cur_index, cur_name))
                cur_index = None
                cur_name = None
        if not entries:
            return False, [], "No images found in WIM"
        return True, entries, "WIM info read successfully"

    @staticmethod
    def dism_apply_image(wim_path: Path, index: int, target_drive: str) -> CmdResult:
        # target_drive e.g., 'W:'
        args = [
            "dism",
            "/Apply-Image",
            f"/ImageFile:{str(wim_path)}",
            f"/Index:{index}",
            f"/ApplyDir:{target_drive}",
            "/Quiet",
        ]
        return SystemOps.run_cmd(args)

    # ------------- bcdboot -------------
    @staticmethod
    def run_bcdboot(windows_drive: str, scheme: str) -> CmdResult:
        if scheme.upper() == "GPT":
            # Copy boot files to ESP (S:) for UEFI
            args = ["bcdboot", f"{windows_drive}\\Windows", "/s", f"{SystemOps.TMP_ESP}:", "/f", "UEFI"]
        else:
            args = ["bcdboot", f"{windows_drive}\\Windows", "/s", f"{windows_drive}", "/f", "BIOS"]
        return SystemOps.run_cmd(args)
