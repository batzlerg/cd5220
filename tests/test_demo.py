import pytest
from unittest.mock import MagicMock, patch
import demo
from cd5220 import CD5220, DisplayMode

@pytest.fixture
def mock_display():
    disp = MagicMock(spec=CD5220)
    disp.current_mode = DisplayMode.NORMAL
    return disp


def test_demo_ascii_invokes_all(monkeypatch, mock_display):
    fake_anim = MagicMock()
    monkeypatch.setattr(demo, "ASCIIAnimations", lambda *a, **k: fake_anim)
    with patch('time.sleep'):
        demo.demo_ascii_animations(mock_display, 0.1)
    fake_anim.play_startup_sequence.assert_called_once()
    fake_anim.play_demo_cycle.assert_called_once()
    mock_display.write_both_lines.assert_any_call('DEMO: ASCII ANIM', 'STARTING...')
