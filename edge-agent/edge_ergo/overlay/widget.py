"""PySide6 Compact Always-on-Top Desktop Overlay for EdgeErgo V3.

Design Requirements:
- Conforms to DESIGN.md §10: Dark charcoal background (#161922), violet accent (#8B5CF6).
- Frameless, always-on-top, non-intrusive.
- Zero Focus Stealing: Configured with Qt.WindowDoesNotAcceptFocus and WA_ShowWithoutActivating.
- Draggable on desktop.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.overlay.settings_dialog import SettingsDialog
from edge_ergo.overlay.types import OVERLAY_STATE_LABELS, OverlayState, OverlayViewModel

STATE_COLORS = {
    OverlayState.READY: "#94A3B8",
    OverlayState.ACTIVE: "#10B981",  # emerald
    OverlayState.PAUSED: "#F59E0B",  # amber
    OverlayState.CAMERA_UNAVAILABLE: "#EF4444",  # rose
    OverlayState.LOW_CONFIDENCE: "#F59E0B",  # amber
    OverlayState.OFFLINE: "#64748B",
    OverlayState.SYNCING: "#3B82F6",  # blue
    OverlayState.AUTH_ERROR: "#EF4444",
    OverlayState.ERROR: "#EF4444",
}


class CompactOverlayWidget(QWidget):
    """Compact frameless always-on-top overlay widget."""

    def __init__(
        self,
        presenter: OverlayPresenter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presenter = presenter
        self._drag_pos = QPoint()

        self._setup_window_flags()
        self._init_ui()
        self.presenter.set_update_callback(self.update_from_vm)
        self.update_from_vm(self.presenter.view_model)

    def _setup_window_flags(self) -> None:
        """Configures frameless always-on-top window with no focus stealing."""
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setFixedSize(320, 210)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Outer Frame
        self.card_frame = QFrame(self)
        self.card_frame.setObjectName("cardFrame")
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        # 1. Header row: State Badge + Sync Status + Controls
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        self.state_badge = QLabel("● Ready")
        self.state_badge.setObjectName("stateBadge")
        header_layout.addWidget(self.state_badge)

        self.sync_label = QLabel("Local only")
        self.sync_label.setObjectName("syncLabel")
        header_layout.addWidget(self.sync_label)

        header_layout.addStretch()

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setObjectName("headerBtn")
        self.pause_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pause_btn.clicked.connect(self._toggle_pause)
        header_layout.addWidget(self.pause_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("headerBtn")
        self.settings_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settings_btn.setToolTip("Open Settings and Privacy Details")
        self.settings_btn.clicked.connect(self._open_settings)
        header_layout.addWidget(self.settings_btn)

        card_layout.addLayout(header_layout)

        # 2. Main Metric Row: Grand Score + Posture Category
        score_layout = QHBoxLayout()
        score_layout.setSpacing(10)

        self.score_label = QLabel("—")
        self.score_label.setObjectName("scoreLabel")
        score_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        self.score_label.setFont(score_font)
        score_layout.addWidget(self.score_label)

        cat_layout = QVBoxLayout()
        cat_layout.setSpacing(2)
        self.cat_title = QLabel("Ergonomic Indicator")
        self.cat_title.setObjectName("catTitle")
        self.cat_value = QLabel("—")
        self.cat_value.setObjectName("catValue")
        cat_layout.addWidget(self.cat_title)
        cat_layout.addWidget(self.cat_value)
        score_layout.addLayout(cat_layout)
        score_layout.addStretch()

        card_layout.addLayout(score_layout)

        # 3. Recommendation Card
        self.rec_label = QLabel("Position yourself naturally in front of your workstation monitor.")
        self.rec_label.setObjectName("recLabel")
        self.rec_label.setWordWrap(True)
        card_layout.addWidget(self.rec_label)

        # 4. Footer: Privacy Guarantee
        self.privacy_label = QLabel("🔒 Camera analysis active — processed on this workstation")
        self.privacy_label.setObjectName("privacyLabel")
        self.privacy_label.setWordWrap(True)
        card_layout.addWidget(self.privacy_label)

        main_layout.addWidget(self.card_frame)

        self._apply_stylesheet()

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                font-family: 'Segoe UI', Inter, -apple-system, sans-serif;
            }
            #cardFrame {
                background-color: #161922;
                border: 1px solid #2A2F42;
                border-radius: 8px;
            }
            #stateBadge {
                font-size: 11px;
                font-weight: 600;
                color: #10B981;
                padding: 2px 6px;
                background-color: rgba(16, 185, 129, 0.12);
                border-radius: 4px;
            }
            #syncLabel {
                font-size: 10px;
                color: #94A3B8;
            }
            #headerBtn {
                background-color: #1F2433;
                color: #F8FAFC;
                border: 1px solid #2A2F42;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 500;
                padding: 2px 6px;
                min-height: 20px;
            }
            #headerBtn:hover {
                background-color: #2A2F42;
            }
            #scoreLabel {
                color: #8B5CF6;
                font-size: 20px;
                font-weight: bold;
            }
            #catTitle {
                font-size: 9px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: #64748B;
                font-weight: 600;
            }
            #catValue {
                font-size: 11px;
                font-weight: 600;
                color: #F8FAFC;
            }
            #recLabel {
                font-size: 10px;
                color: #CBD5E1;
                background-color: rgba(31, 36, 51, 0.6);
                border-radius: 4px;
                padding: 4px 6px;
                line-height: 1.3;
            }
            #privacyLabel {
                font-size: 9px;
                color: #64748B;
            }
        """)

    def update_from_vm(self, vm: OverlayViewModel) -> None:
        """Updates GUI elements from pure OverlayViewModel."""
        color = STATE_COLORS.get(vm.state, "#94A3B8")
        label = OVERLAY_STATE_LABELS.get(vm.state, "Unknown")
        self.state_badge.setText(f"● {label}")
        self.state_badge.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {color}; "
            f"background-color: rgba(255, 255, 255, 0.05); border-radius: 4px; padding: 2px 6px;"
        )

        self.score_label.setText(vm.score_text)
        self.cat_value.setText(vm.category_text)
        self.rec_label.setText(vm.recommendation)
        sync_text = (
            f"{vm.sync_status_text} (Q:{vm.queue_depth})"
            if vm.queue_depth > 0
            else vm.sync_status_text
        )
        self.sync_label.setText(sync_text)
        self.sync_label.setToolTip(
            f"Sync State: {vm.sync_status_text} | "
            f"Queue Depth: {vm.queue_depth} | Last Sync: {vm.last_sync_text}"
        )
        self.pause_btn.setText("Resume" if vm.is_paused else "Pause")

    def _toggle_pause(self) -> None:
        self.presenter.toggle_pause()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.presenter, self)
        dlg.exec()

    # Drag-to-reposition logic
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
