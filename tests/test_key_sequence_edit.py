from unittest.mock import MagicMock

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent

from src.ui.settings_ui import KeySequenceEdit

# qapp fixture is provided by conftest.py

def test_signal_emission(qapp):
    """Test that recording status signal is emitted correctly"""
    obj = KeySequenceEdit()
    mock_slot = MagicMock()
    obj.recording_toggled.connect(mock_slot)

    # Test True
    obj.setIsRecording(True)
    assert obj.recording is True
    mock_slot.assert_called_with(True)

    mock_slot.reset_mock()

    # Test False
    obj.setIsRecording(False)
    assert obj.recording is False
    mock_slot.assert_called_with(False)

def test_ctrl_key_behavior(qapp):
    """Test that modifier keys alone do not stop recording"""
    obj = KeySequenceEdit()
    obj.setIsRecording(True)

    # Press Ctrl
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier)
    obj.keyPressEvent(event)

    # Should persist recording
    assert obj.recording is True

    # Press A (with Ctrl mod)
    event2 = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier, "a")
    obj.keyPressEvent(event2)

    # Should stop recording
    assert obj.recording is False
    assert obj.text().lower() == "ctrl+a"

def test_set_mode_preserves_recording(qapp):
    """Verify that calling setMode with same mode does not reset recording state"""
    edit = KeySequenceEdit()
    edit.setIsRecording(True)
    assert edit.recording is True

    # Calling setMode('key') again should NOT reset recording
    edit.setMode("key")
    assert edit.recording is True

def test_preview_update_loop_regression(qapp):
    """Regression test for the loop where setText triggers update_preview triggers setMode"""
    edit = KeySequenceEdit()

    # Mocking the _update_preview behavior using connection
    def update_preview():
        edit.setMode("key")

    edit.textChanged.connect(update_preview)

    # Start recording
    edit.setIsRecording(True)

    # Simulate pressing "Ctrl" which updates text
    edit.setText("ctrl")

    # Assert: Recording should still be True
    assert edit.recording is True, "Recording should persist through text updates and setMode calls"
