import sys
import ctypes
import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QProgressBar,
    QGroupBox,
    QMessageBox,
    QRadioButton,
)

# These modules will be implemented in subsequent steps
from .system import SystemOps  # type: ignore
from .tasks import DismInfoWorker, DeployWorker  # type: ignore

APP_NAME = "Windows Image Deployment — Mirza Hasnain Baig"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_as_admin():
    # Relaunch this module elevated: python -m app.main
    params = "-m app.main"
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1024, 700)
        self.setWindowIcon(QIcon())

        # State
        self.source_path: Path | None = None
        self.install_wim_path: Path | None = None
        self.index_map: list[tuple[int, str]] = []

        self._setup_logging()
        self._build_ui()
        self._apply_style()
        self._refresh_disks()

    def _setup_logging(self):
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "app.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_path, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.log_path = log_path

    def _apply_style(self):
        # Simple modern dark style
        self.setStyleSheet(
            """
            QWidget { font-family: 'Segoe UI', Arial; font-size: 10.5pt; }
            QMainWindow { background: #0f1419; }
            QGroupBox { color: #d7d7d7; border: 1px solid #22303a; border-radius: 8px; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLabel { color: #cbd5e1; }
            QLineEdit, QComboBox, QTextEdit { background: #111827; color: #e5e7eb; border: 1px solid #374151; border-radius: 6px; padding: 6px; }
            QPushButton { background: #2563eb; color: white; padding: 8px 14px; border-radius: 6px; }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #374151; color: #9ca3af; }
            QRadioButton { color: #e5e7eb; }
            QProgressBar { border: 1px solid #374151; border-radius: 6px; text-align: center; }
            QProgressBar::chunk { background-color: #10b981; }
            """
        )

    def _build_ui(self):
        cw = QWidget()
        root = QVBoxLayout(cw)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # 1. Source selection
        src_box = QGroupBox("1. Source Image (ISO or install.wim)")
        src_layout = QVBoxLayout()
        self.src_line = QLineEdit()
        self.src_line.setReadOnly(True)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._on_browse_source)
        l1 = QHBoxLayout()
        l1.addWidget(self.src_line, 1)
        l1.addWidget(btn_browse)

        self.cbo_index = QComboBox()
        self.cbo_index.setPlaceholderText("Select Windows edition (index)")
        btn_refresh_index = QPushButton("Read WIM Info")
        btn_refresh_index.clicked.connect(self._on_read_wim_info)
        l2 = QHBoxLayout()
        l2.addWidget(self.cbo_index, 1)
        l2.addWidget(btn_refresh_index)

        src_layout.addLayout(l1)
        src_layout.addLayout(l2)
        src_box.setLayout(src_layout)

        # 2. Disk selection
        disk_box = QGroupBox("2. Target Disk and Partitioning")
        disk_layout = QVBoxLayout()
        self.cbo_disks = QComboBox()
        self.rb_gpt = QRadioButton("GPT (UEFI)")
        self.rb_mbr = QRadioButton("MBR (Legacy)")
        self.rb_gpt.setChecked(True)
        scheme_row = QHBoxLayout()
        scheme_row.addWidget(self.rb_gpt)
        scheme_row.addWidget(self.rb_mbr)
        btn_refresh_disks = QPushButton("Scan Disks")
        btn_refresh_disks.clicked.connect(self._refresh_disks)
        disk_layout.addWidget(self.cbo_disks)
        disk_layout.addLayout(scheme_row)
        disk_layout.addWidget(btn_refresh_disks)
        disk_box.setLayout(disk_layout)

        # 3. Deploy
        deploy_box = QGroupBox("3. Deploy")
        deploy_layout = QVBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.btn_deploy = QPushButton("Deploy")
        self.btn_deploy.clicked.connect(self._on_deploy)
        deploy_layout.addWidget(self.progress)
        deploy_layout.addWidget(self.btn_deploy)
        deploy_box.setLayout(deploy_layout)

        # Log output
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(200)

        root.addWidget(src_box)
        root.addWidget(disk_box)
        root.addWidget(deploy_box)
        root.addWidget(QLabel("Log:"))
        root.addWidget(self.txt_log, 1)

        self.setCentralWidget(cw)

    def append_log(self, text: str):
        logging.info(text)
        self.txt_log.append(text)

    def _on_browse_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ISO or install.wim",
            str(Path.home()),
            "ISO/WIM Files (*.iso *.wim);;All Files (*.*)",
        )
        if not path:
            return
        self.source_path = Path(path)
        self.append_log(f"Selected source: {self.source_path}")
        if self.source_path.suffix.lower() == ".wim":
            self.install_wim_path = self.source_path
        elif self.source_path.suffix.lower() == ".iso":
            self.install_wim_path = None
        else:
            QMessageBox.warning(self, APP_NAME, "Unsupported file type. Select .iso or .wim")
            return
        self.src_line.setText(str(self.source_path))

    def _on_read_wim_info(self):
        if not self.source_path:
            QMessageBox.warning(self, APP_NAME, "Select a source ISO or WIM first.")
            return
        self.cbo_index.clear()
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.btn_deploy.setEnabled(False)

        self.info_worker = DismInfoWorker(self.source_path)
        self.info_worker.log.connect(self.append_log)
        self.info_worker.completed.connect(self._on_wim_info_ready)
        self.info_worker.start()

    def _on_wim_info_ready(self, ok: bool, message: str, entries: list[tuple[int, str]], wim_path: str):
        self.progress.setVisible(False)
        self.btn_deploy.setEnabled(True)
        if not ok:
            QMessageBox.critical(self, APP_NAME, message)
            return
        self.install_wim_path = Path(wim_path)
        self.index_map = entries
        for idx, name in entries:
            self.cbo_index.addItem(f"{idx}: {name}", idx)
        self.append_log(message)

    def _refresh_disks(self):
        self.cbo_disks.clear()
        self.append_log("Scanning disks…")
        try:
            disks = SystemOps.list_disks()
        except Exception as ex:
            self.append_log(f"Disk scan failed: {ex}")
            QMessageBox.critical(self, APP_NAME, f"Disk scan failed: {ex}")
            return
        for d in disks:
            label = f"Disk {d['Number']} - {d['SizeGB']} GB - {d['Model']} ({d['Style']})"
            self.cbo_disks.addItem(label, d["Number"])
        self.append_log(f"Found {len(disks)} disk(s)")

    def _confirm_destructive(self) -> bool:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(APP_NAME)
        msg.setText(
            "WARNING: This will CLEAN and repartition the selected disk. This is destructive. Continue?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        ret = msg.exec()
        return ret == QMessageBox.Yes

    def _on_deploy(self):
        if not self.install_wim_path:
            QMessageBox.warning(self, APP_NAME, "WIM not resolved. Read WIM Info first.")
            return
        if self.cbo_disks.count() == 0:
            QMessageBox.warning(self, APP_NAME, "No disk selected.")
            return
        idx = self.cbo_index.currentData()
        if idx is None:
            QMessageBox.warning(self, APP_NAME, "Select a WIM index.")
            return
        disk_number = int(self.cbo_disks.currentData())
        scheme = "GPT" if self.rb_gpt.isChecked() else "MBR"

        if not self._confirm_destructive():
            self.append_log("User canceled destructive action.")
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.btn_deploy.setEnabled(False)

        self.deploy_worker = DeployWorker(
            source=self.source_path,
            wim_path=self.install_wim_path,
            index=int(idx),
            disk_number=disk_number,
            scheme=scheme,
        )
        self.deploy_worker.log.connect(self.append_log)
        self.deploy_worker.completed.connect(self._on_deploy_done)
        self.deploy_worker.start()

    def _on_deploy_done(self, ok: bool, message: str):
        self.progress.setVisible(False)
        self.btn_deploy.setEnabled(True)
        if ok:
            QMessageBox.information(self, APP_NAME, message)
        else:
            QMessageBox.critical(self, APP_NAME, message)


def main():
    if not is_admin():
        run_as_admin()
        return
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.setApplicationName(APP_NAME)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
