import pytest
from unittest.mock import Mock, patch

from cd5220 import (
    ASCIIAnimator,
    bouncing_ball_animation,
    progress_bar_animation,
    spinning_loader,
    wave_animation,
    matrix_rain_animation,
    typewriter_animation,
    pulsing_alert,
    CD5220ASCIIAnimations,
)


@pytest.fixture
def mock_display():
    display = Mock()
    display.write_both_lines = Mock()
    display.write_positioned = Mock()
    display.write_viewport = Mock()
    display.set_window = Mock()
    display.enter_viewport_mode = Mock()
    display.cancel_current_line = Mock()
    display.clear_window = Mock()
    display.set_brightness = Mock()
    return display


@pytest.fixture
def animator(mock_display):
    return ASCIIAnimator(
        mock_display,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
    )


def test_animator_buffer_operations(animator):
    animator.set_char(0, 0, 'A')
    assert animator.frame_buffer[0][0] == 'A'
    animator.clear_buffer()
    assert all(ch == ' ' for row in animator.frame_buffer for ch in row)


def test_render_frame_calls_display(animator):
    animator.set_char(0, 0, 'A')
    animator.set_char(0, 1, 'B')
    animator.render_frame()
    assert animator.display.write_both_lines.called or animator.display.write_positioned.called


def test_basic_animations_call_write(animator):
    bouncing_ball_animation(animator, duration=0.1)
    progress_bar_animation(animator, duration=0.1)
    spinning_loader(animator, duration=0.1)
    wave_animation(animator, duration=0.1)
    matrix_rain_animation(animator, duration=0.1)
    assert animator.display.write_both_lines.called or animator.display.write_positioned.called


def test_typewriter_and_pulse_use_display(animator):
    typewriter_animation(animator, 'TEST', line=0)
    pulsing_alert(animator, 'ALERT', duration=0.2)
    assert animator.display.write_both_lines.called or animator.display.write_positioned.called
    assert animator.display.set_brightness.called


def test_wrapper_instantiation(mock_display):
    library = CD5220ASCIIAnimations(
        mock_display,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
    )
    assert library.display is mock_display
    assert isinstance(library.animator, ASCIIAnimator)

def test_custom_sleep_functions(animator, mock_display):
    sleep_calls = []
    frame_calls = []
    animator = ASCIIAnimator(
        mock_display,
        sleep_fn=lambda s: sleep_calls.append(s),
        frame_sleep_fn=lambda s: frame_calls.append(s),
        frame_rate=2,
    )
    bouncing_ball_animation(animator, duration=0.5)
    assert frame_calls


def test_spinning_loader_uses_viewport(animator):
    spinning_loader(animator, duration=0.3)
    display = animator.display
    assert display.set_window.called
    assert display.enter_viewport_mode.called
    assert display.write_viewport.called
    assert display.cancel_current_line.called
    assert display.clear_window.called

