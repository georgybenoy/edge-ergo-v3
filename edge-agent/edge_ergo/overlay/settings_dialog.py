"""PySide6 Settings, Privacy, and Device Enrollment Dialog for EdgeErgo V3."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.storage.database import Database
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.sync.enrollment import enroll_device, forget_device

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """User configuration dialog with privacy explanations and device enrollment controls."""

    def __init__(
        self,
        presenter: OverlayPresenter,
        parent: QWidget | None = None,
        repository: StorageRepository | None = None,
    ) -> None:
        super().__init__(parent)
        self.presenter = presenter
        self.repo = repository or StorageRepository(Database())

        self.setWindowTitle("EdgeErgo Settings & Device Enrollment")
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._init_ui()
        self._load_current_values()
        self._refresh_enrollment_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # 1. Monitoring Preferences Group
        pref_group = QGroupBox("Workstation Ergonomic Preferences")
        form = QFormLayout(pref_group)
        form.setSpacing(10)

        self.sampling_spin = QDoubleSpinBox()
        self.sampling_spin.setRange(1.0, 60.0)
        self.sampling_spin.setSingleStep(1.0)
        self.sampling_spin.setSuffix(" s")
        self.sampling_spin.setToolTip("Frequency at which the camera analyzes posture.")
        form.addRow("Sampling Interval:", self.sampling_spin)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(1, 120)
        self.cooldown_spin.setSingleStep(5)
        self.cooldown_spin.setSuffix(" min")
        self.cooldown_spin.setToolTip("Minimum delay between proactive ergonomic recommendations.")
        form.addRow("Reminder Cooldown:", self.cooldown_spin)

        self.quiet_check = QCheckBox("Enable Quiet Mode")
        self.quiet_check.setToolTip(
            "Suppresses proactive recommendation prompts while preserving telemetry."
        )
        form.addRow("", self.quiet_check)

        layout.addWidget(pref_group)

        # 2. Enterprise Device Enrollment Group
        self.enroll_group = QGroupBox("Enterprise Cloud Synchronization")
        self.enroll_layout = QVBoxLayout(self.enroll_group)
        self.enroll_layout.setSpacing(8)

        self.enroll_status_label = QLabel("Loading enrollment status...")
        self.enroll_status_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.enroll_layout.addWidget(self.enroll_status_label)

        # Inputs for un-enrolled device
        self.enroll_form_widget = QWidget()
        form_enroll = QFormLayout(self.enroll_form_widget)
        form_enroll.setContentsMargins(0, 0, 0, 0)
        form_enroll.setSpacing(8)

        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://api.yourcompany.com")
        form_enroll.addRow("Server URL:", self.api_url_input)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("eet_...")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_enroll.addRow("Enrollment Token:", self.token_input)

        self.enroll_layout.addWidget(self.enroll_form_widget)

        # Actions for enrollment
        self.enroll_action_layout = QHBoxLayout()
        self.enroll_btn = QPushButton("Enroll Workstation")
        self.enroll_btn.clicked.connect(self._handle_enroll)
        self.enroll_action_layout.addWidget(self.enroll_btn)

        self.forget_btn = QPushButton("Forget Workstation")
        self.forget_btn.clicked.connect(self._handle_forget)
        self.forget_btn.setStyleSheet("color: #EF4444; border-color: #EF4444;")
        self.enroll_action_layout.addWidget(self.forget_btn)

        self.enroll_action_layout.addStretch()
        self.enroll_layout.addLayout(self.enroll_action_layout)

        layout.addWidget(self.enroll_group)

        # 3. Privacy Architecture (FR-024)
        privacy_group = QGroupBox("Privacy Architecture (FR-024)")
        privacy_layout = QVBoxLayout(privacy_group)
        privacy_layout.setSpacing(6)

        local_label = QLabel(
            "<b>Strictly Local On This Workstation:</b><br>"
            "• Real-time webcam video frames (processed exclusively in volatile RAM).<br>"
            "• 33 normalized anatomical pose landmark coordinates.<br>"
            "• <i>Guaranteed: Zero video recordings or images are ever stored or transmitted.</i>"
        )
        local_label.setTextFormat(Qt.TextFormat.RichText)
        local_label.setWordWrap(True)
        local_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        privacy_layout.addWidget(local_label)

        sync_label = QLabel(
            "<b>Synchronized With Enterprise Dashboard:</b><br>"
            "• Aggregated numerical ergonomic indicator (e.g. RULA score 1–7).<br>"
            "• Categorical guidance codes (e.g. GUID_NECK_FLEX_01).<br>"
            "• Workstation device public identifier and timestamp."
        )
        sync_label.setTextFormat(Qt.TextFormat.RichText)
        sync_label.setWordWrap(True)
        sync_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        privacy_layout.addWidget(sync_label)

        layout.addWidget(privacy_group)

        # 4. Dialog Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Preferences")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

        # Dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #161922;
                color: #F8FAFC;
            }
            QGroupBox {
                border: 1px solid #2A2F42;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
                font-weight: 600;
                color: #F8FAFC;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #F8FAFC;
            }
            QLineEdit, QDoubleSpinBox, QSpinBox {
                background-color: #1F2433;
                color: #F8FAFC;
                border: 1px solid #2A2F42;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QCheckBox {
                color: #F8FAFC;
            }
            QPushButton {
                background-color: #2A2F42;
                color: #F8FAFC;
                border: 1px solid #3B425A;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #373E57;
            }
            QPushButton[default="true"] {
                background-color: #8B5CF6;
                border-color: #7C3AED;
            }
            QPushButton[default="true"]:hover {
                background-color: #7C3AED;
            }
        """)

    def _refresh_enrollment_ui(self) -> None:
        identity = self.repo.get_device_identity()
        if identity is not None:
            self.enroll_status_label.setText(
                f"<b>Status:</b> Enrolled<br>"
                f"<b>Public ID:</b> {identity.public_id}<br>"
                f"<b>Server:</b> {identity.api_base_url}<br>"
                f"<b>Workstation Label:</b> {identity.label}"
            )
            self.enroll_status_label.setTextFormat(Qt.TextFormat.RichText)
            self.enroll_form_widget.setVisible(False)
            self.enroll_btn.setVisible(False)
            self.forget_btn.setVisible(True)
        else:
            self.enroll_status_label.setText(
                "<b>Status:</b> Not enrolled (Telemetry stored locally only)"
            )
            self.enroll_status_label.setTextFormat(Qt.TextFormat.RichText)
            self.enroll_form_widget.setVisible(True)
            self.enroll_btn.setVisible(True)
            self.forget_btn.setVisible(False)

    def _handle_enroll(self) -> None:
        url = self.api_url_input.text().strip()
        token = self.token_input.text().strip()
        if not url or not token:
            self.enroll_status_label.setText("Error: Server URL and Token are both required.")
            return

        try:
            enroll_device(api_base_url=url, token=token, repo=self.repo)
            self.token_input.clear()
            self._refresh_enrollment_ui()
            self.presenter.on_sync_status_changed("Enrolled")
        except Exception as exc:
            self.enroll_status_label.setText(f"Enrollment Error: {exc}")

    def _handle_forget(self) -> None:
        forget_device(repo=self.repo)
        self._refresh_enrollment_ui()
        self.presenter.on_sync_status_changed("Local only")

    def _load_current_values(self) -> None:
        vm = self.presenter.view_model
        self.sampling_spin.setValue(vm.sampling_interval_s)
        self.cooldown_spin.setValue(vm.reminder_cooldown_min)
        self.quiet_check.setChecked(vm.is_quiet_mode)

    def _save_and_close(self) -> None:
        self.presenter.update_settings(
            sampling_interval_s=self.sampling_spin.value(),
            reminder_cooldown_min=self.cooldown_spin.value(),
            quiet_mode=self.quiet_check.isChecked(),
        )
        self.accept()
