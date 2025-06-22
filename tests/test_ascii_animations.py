import pytest
from unittest.mock import Mock, patch

from cd5220 import (
    DiffAnimator,
    CD5220,
    DisplaySimulator,
    bouncing_ball_animation,
    progress_bar_animation,
    spinning_loader,
    wave_animation,
    matrix_rain_animation,
    spinner_tapestry,
    cloud_conveyor,
    zen_breathing,
    firework_bursts,
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
    return DiffAnimator(
        mock_display,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        enable_simulator=True,
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
    assert animator.display.write_positioned.called
    assert not animator.display.write_both_lines.called


def test_basic_animations_call_write(animator):
    bouncing_ball_animation(animator, duration=0.1)
    progress_bar_animation(animator, duration=0.1)
    spinning_loader(animator, duration=0.1)
    wave_animation(animator, duration=0.1)
    matrix_rain_animation(animator, duration=0.1)
    spinner_tapestry(animator, duration=0.1)
    cloud_conveyor(animator, duration=0.1)
    zen_breathing(animator, duration=0.1)
    firework_bursts(animator, duration=0.1)
    assert animator.display.write_positioned.called
    assert not animator.display.write_both_lines.called


def test_typewriter_and_pulse_use_display(animator):
    typewriter_animation(animator, 'TEST', line=0)
    pulsing_alert(animator, 'ALERT', duration=0.2)
    assert animator.display.write_positioned.called
    assert not animator.display.write_both_lines.called
    assert animator.display.set_brightness.called


def test_wrapper_instantiation(mock_display):
    library = CD5220ASCIIAnimations(
        mock_display,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        render_console=False,
    )
    assert library.display is mock_display
    assert isinstance(library.animator, DiffAnimator)

def test_custom_sleep_functions(animator, mock_display):
    sleep_calls = []
    frame_calls = []
    animator = DiffAnimator(
        mock_display,
        sleep_fn=lambda s: sleep_calls.append(s),
        frame_sleep_fn=lambda s: frame_calls.append(s),
        frame_rate=2,
        enable_simulator=True,
    )
    bouncing_ball_animation(animator, duration=0.5)
    assert frame_calls


def test_spinning_loader_updates_spinner_only(animator):
    spinning_loader(animator, duration=0.2)
    display = animator.display
    # Should not use viewport or string mode helpers
    assert not display.set_window.called
    assert not display.enter_viewport_mode.called
    assert not display.write_viewport.called
    # Spinner updates use write_positioned
    assert display.write_positioned.called


def test_progress_bar_exits_string_mode():
    with patch('cd5220.serial.Serial') as mock_serial:
        mock_serial.return_value.is_open = True
        display = CD5220('mock', debug=False, initialization_delay=0)
        display.ser = mock_serial.return_value

        animator = DiffAnimator(
            display,
            sleep_fn=lambda _ : None,
            frame_sleep_fn=lambda _ : None,
            enable_simulator=True,
        )

        with patch.object(display, 'write_both_lines') as wb, \
             patch.object(display, 'write_positioned') as wp, \
             patch.object(display, 'cancel_current_line') as cc, \
             patch.object(display, 'clear_display') as cd:
            progress_bar_animation(animator, duration=0.1)
            assert not wb.called
            assert cd.call_count == 0


def test_display_simulator_diff():
    sim = DisplaySimulator()
    sim.apply_frame("HELLO", "WORLD")
    changes = list(sim.diff(["HELLO", "THERE"]))
    assert (0, 1, 'T') in changes


def test_progress_bar_static_elements(animator):
    progress_bar_animation(animator, duration=0.1)
    sim = animator.simulator
    assert sim is not None
    sim.assert_char_at(4, 1, '[')
    sim.assert_char_at(15, 1, ']')


def test_simulator_assertions_and_access(mock_display):
    animator = DiffAnimator(mock_display, enable_simulator=False,
                            sleep_fn=lambda _: None, frame_sleep_fn=lambda _: None)
    assert animator.get_simulator() is None
    animator.enable_testing_mode()
    sim = animator.get_simulator()
    assert isinstance(sim, DisplaySimulator)
    progress_bar_animation(animator, duration=0.1)
    sim.assert_line_contains(0, "COMPLETE")
    sim.assert_line_equals(1, "    [==========]    ")
    sim.assert_static_preserved([(4, 1, '['), (15, 1, ']')])
    assert "Line 1:" in sim.dump()


def test_console_render_outputs_frames(capsys, mock_display):
    animator = DiffAnimator(
        mock_display,
        enable_simulator=False,
        render_console=True,
        sleep_fn=lambda _: None,
        frame_sleep_fn=lambda _: None,
    )
    animator.write_frame("HELLO", "WORLD")
    out1 = capsys.readouterr().out
    sep = "-" * 20
    assert sep in out1
    assert "HELLO" in out1
    assert "WORLD" in out1
    animator.write_frame("BYE", "NOW")
    out2 = capsys.readouterr().out
    # console render should update in place with escape sequences
    assert sep in out2
    assert "BYE" in out2


