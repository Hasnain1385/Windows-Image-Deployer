from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from .system import SystemOps


class DismInfoWorker(QThread):
    log = Signal(str)
    completed = Signal(bool, str, list, str)  # ok, message, entries, wim_path

    def __init__(self, source_path: Path):
        super().__init__()
        self.source_path = source_path

    def run(self):
        try:
            from_iso, wim_path, mount_root, err = SystemOps.resolve_wim_from_source(self.source_path)
            if err:
                self.completed.emit(False, err, [], "")
                return
            assert wim_path is not None
            ok, entries, msg = SystemOps.dism_get_wim_info(wim_path)
            if not ok:
                # Cleanup mount if needed
                if from_iso:
                    SystemOps.unmount_iso(self.source_path)
                self.completed.emit(False, msg, [], "")
                return
            self.completed.emit(True, msg, entries, str(wim_path))
        except Exception as ex:
            self.completed.emit(False, str(ex), [], "")


class DeployWorker(QThread):
    log = Signal(str)
    completed = Signal(bool, str)

    def __init__(self, source: Path, wim_path: Path, index: int, disk_number: int, scheme: str):
        super().__init__()
        self.source = source
        self.wim_path = wim_path
        self.index = index
        self.disk_number = disk_number
        self.scheme = scheme.upper()

    def run(self):
        try:
            # Ensure WIM available (mount ISO if needed)
            from_iso = False
            if self.source.suffix.lower() == ".iso":
                ok, mount_root, err = SystemOps.mount_iso(self.source)
                if not ok:
                    self.completed.emit(False, f"ISO mount failed: {err}")
                    return
                from_iso = True

            # Prepare disk
            self.log.emit("Preparing disk with DiskPart…")
            if self.scheme == "GPT":
                res = SystemOps.prepare_disk_gpt(self.disk_number)
            else:
                res = SystemOps.prepare_disk_mbr(self.disk_number)
            if not res.ok:
                if from_iso:
                    SystemOps.unmount_iso(self.source)
                self.completed.emit(False, f"DiskPart failed: {res.err or res.out}")
                return
            self.log.emit(res.out)

            # Apply image
            self.log.emit("Applying image with DISM… This can take a while.")
            res = SystemOps.dism_apply_image(self.wim_path, self.index, f"{SystemOps.TMP_WIN}:")
            if not res.ok:
                if from_iso:
                    SystemOps.unmount_iso(self.source)
                self.completed.emit(False, f"DISM apply failed: {res.err or res.out}")
                return
            self.log.emit("Image applied successfully.")

            # bcdboot
            self.log.emit("Configuring boot files (bcdboot)…")
            res = SystemOps.run_bcdboot(f"{SystemOps.TMP_WIN}:", self.scheme)
            if not res.ok:
                if from_iso:
                    SystemOps.unmount_iso(self.source)
                self.completed.emit(False, f"bcdboot failed: {res.err or res.out}")
                return
            self.log.emit("Boot files created successfully.")

            # Cleanup letters
            self.log.emit("Cleaning up temporary drive letters…")
            try:
                SystemOps.cleanup_letters(self.disk_number)
            except Exception:
                pass

            # Unmount ISO if needed
            if from_iso:
                SystemOps.unmount_iso(self.source)

            self.completed.emit(True, "Deployment completed successfully.")
        except Exception as ex:
            self.completed.emit(False, str(ex))
