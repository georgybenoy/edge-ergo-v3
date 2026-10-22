"""Tests for camera capture subsystem and privacy invariants (FR-001, FR-007)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from edge_ergo.camera.fake_source import FakeCameraSource
from edge_ergo.camera.types import (
    CameraFrame,
    CameraPermissionError,
    CameraState,
)


def test_fake_camera_lifecycle() -> None:
    """Verifies open, read, pause, resume, and close lifecycle of FakeCameraSource."""
    cam = FakeCameraSource(width=640, height=480, fps=30.0)
    assert not cam.is_open()
    assert cam.get_state() == CameraState.UNINITIALIZED

    assert cam.open() is True
    assert cam.is_open()
    assert cam.get_state() == CameraState.ACTIVE

    # Read frame
    frame = cam.read_frame()
    assert frame is not None
    assert isinstance(frame, CameraFrame)
    assert frame.width == 640
    assert frame.height == 480
    assert frame.data.shape == (480, 640, 3)
    assert frame.data.dtype.name == "uint8"
    assert frame.frame_id == 1

    # Pause
    cam.pause()
    assert cam.get_state() == CameraState.PAUSED
    assert cam.read_frame() is None

    # Resume
    cam.resume()
    assert cam.get_state() == CameraState.ACTIVE
    frame2 = cam.read_frame()
    assert frame2 is not None
    assert frame2.frame_id == 2

    # Close
    cam.close()
    assert not cam.is_open()
    assert cam.get_state() == CameraState.CLOSED
    assert cam.read_frame() is None


def test_fake_camera_permission_denied() -> None:
    """Verifies typed exception mapping when camera access is denied."""
    cam = FakeCameraSource(simulate_permission_denied=True)
    with pytest.raises(CameraPermissionError, match="permission denied"):
        cam.open()
    assert cam.get_state() == CameraState.PERMISSION_DENIED


def test_fake_camera_simulated_disconnect() -> None:
    """Verifies disconnected state when camera drops after N frames."""
    cam = FakeCameraSource(simulate_disconnect_after=2)
    cam.open()

    f1 = cam.read_frame()
    assert f1 is not None
    f2 = cam.read_frame()
    assert f2 is not None

    # Third frame triggers simulated disconnect
    f3 = cam.read_frame()
    assert f3 is None
    assert cam.get_state() == CameraState.DISCONNECTED
    cam.close()


def test_camera_frame_repr_redaction() -> None:
    """Ensures raw pixel matrices are strictly redacted from string and repr output."""
    cam = FakeCameraSource()
    cam.open()
    frame = cam.read_frame()
    assert frame is not None

    rep = repr(frame)
    str_rep = str(frame)

    assert "pixels redacted" in rep
    assert "in-memory only" in rep
    assert "array(" not in rep
    assert "uint8" not in rep
    assert rep == str_rep
    cam.close()


def test_zero_disk_writes_during_capture(tmp_path: Path) -> None:
    """Critical Privacy Test (FR-007):

    Scans the filesystem before and after simulated camera capture runs
    to guarantee that ZERO image or video files are written to disk.
    """
    media_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".avi",
        ".mp4",
        ".mov",
        ".mkv",
        ".raw",
        ".webm",
    }

    # Track pre-existing files in temp directory
    temp_dir = Path(tempfile.gettempdir())
    cwd = Path.cwd()

    def find_media_files(root: Path) -> set[Path]:
        found: set[Path] = set()
        try:
            for p in root.rglob("*"):
                if p.is_file() and p.suffix.lower() in media_extensions:
                    found.add(p)
        except Exception:
            pass
        return found

    pre_files_cwd = find_media_files(cwd)
    pre_files_temp = find_media_files(temp_dir)

    # Run 25 frames through FakeCameraSource
    cam = FakeCameraSource(width=320, height=240)
    cam.open()
    for _ in range(25):
        frame = cam.read_frame()
        assert frame is not None
        # Hold frame in memory, compute a dummy operation, and discard
        _ = frame.data.mean()
        del frame
    cam.close()

    # Scan after capture
    post_files_cwd = find_media_files(cwd)
    post_files_temp = find_media_files(temp_dir)

    new_cwd_media = post_files_cwd - pre_files_cwd
    new_temp_media = post_files_temp - pre_files_temp

    assert not new_cwd_media, f"Prohibited media files written to cwd: {new_cwd_media}"
    assert not new_temp_media, f"Prohibited media files written to temp: {new_temp_media}"
