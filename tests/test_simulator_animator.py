from unittest.mock import Mock, patch

import pytest

from cd5220 import DisplaySimulator, DiffAnimator, CD5220, DisplayMode


def test_display_simulator_apply_and_diff():
    sim = DisplaySimulator()
    sim.apply_frame("HELLO", "WORLD")
    assert sim.get_line(1).startswith("HELLO")
    assert sim.get_line(2).startswith("WORLD")
    # diff against a slightly modified frame
    changes = list(sim.diff(["HELXO", "WORLD"]))
    assert (4, 1, "X") in changes
    assert sim.frame_history


def test_display_simulator_state_assertions():
    sim = DisplaySimulator()
    sim.set_brightness_level(2)
    sim.set_display_on(False)
    sim.set_cursor_visible(True)
    sim.assert_brightness(2)
    sim.assert_display_on(False)
    sim.assert_cursor_visible(True)


def test_diff_animator_clear_and_reset():
    display = Mock()
    animator = DiffAnimator(display, enable_simulator=True,
                            sleep_fn=lambda _: None, frame_sleep_fn=lambda _: None)
    animator.set_char(0, 0, "A")
    animator.render_frame()
    assert animator.simulator.get_line(1)[0] == "A"
    animator.clear_display()
    display.clear_display.assert_called_once()
    assert animator.simulator.get_line(1).strip() == ""
    assert all(all(ch == " " for ch in row) for row in animator.buffer)


def test_diff_animator_enable_testing_mode():
    display = Mock()
    animator = DiffAnimator(display, enable_simulator=False,
                            sleep_fn=lambda _: None, frame_sleep_fn=lambda _: None)
    assert animator.get_simulator() is None
    animator.enable_testing_mode()
    assert animator.get_simulator() is not None


def test_diff_animator_console_render(capsys):
    display = Mock()
    animator = DiffAnimator(display, enable_simulator=True, render_console=True,
                            sleep_fn=lambda _: None, frame_sleep_fn=lambda _: None)
    animator.write_frame("HELLO", "WORLD")
    out1 = capsys.readouterr().out
    assert "HELLO" in out1
    animator.write_frame("BYE", "NOW")
    out2 = capsys.readouterr().out
    assert "BYE" in out2
    # ensure frame separator printed
    assert "-" * 20 in out2




def test_display_message_normal_mode():
    disp = CD5220.create_simulator_only(debug=False)
    with patch('time.sleep') as ts:
        disp.display_message('HELLO WORLD 1234567890', duration=0.0, mode='normal')
        ts.assert_called_with(0.0)
    sim = disp.simulator
    sim.assert_line_contains(1, 'HELLO')
    sim.assert_line_contains(2, '90')


def test_cursor_movement_commands():
    disp = CD5220.create_simulator_only(debug=False)
    disp.set_cursor_position(1, 1)
    disp.write_at_cursor('A')
    disp.cursor_move_right()
    disp.write_at_cursor('B')
    disp.cursor_move_left()
    disp.write_at_cursor('C')
    sim = disp.simulator
    sim.assert_char_at(1, 1, 'A')
    sim.assert_char_at(3, 1, 'C')


def test_enable_console_render_method(capsys):
    display = Mock()
    animator = DiffAnimator(display, enable_simulator=False,
                            sleep_fn=lambda _: None, frame_sleep_fn=lambda _: None)
    animator.enable_console_render()
    assert animator.render_console
    animator.write_frame('HI', 'THERE')
    out = capsys.readouterr().out
    assert 'HI' in out

def test_initialize_and_restore_defaults():
    disp = CD5220.create_simulator_only(debug=False)
    disp.set_brightness(2)
    disp.write_upper_line('HELLO')
    disp.set_window(1, 1, 5)
    disp.enter_viewport_mode()
    disp.initialize(delay=0.0)
    assert disp.current_mode == DisplayMode.NORMAL
    assert disp.active_window is None
    disp.restore_defaults(delay=0.0)
    assert disp.current_mode == DisplayMode.NORMAL
    assert disp.active_window is None


def test_display_on_off_and_home():
    disp = CD5220.create_simulator_only(debug=False)
    disp.write_upper_line('TEST')
    disp.display_off()
    disp.display_on()
    disp.cursor_home()
    disp.write_at_cursor('A')
    sim = disp.simulator
    sim.assert_char_at(1, 1, 'A')


def test_console_render_no_change(capsys):
    animator = DiffAnimator(Mock(), enable_simulator=True, render_console=True,
                             sleep_fn=lambda _: None, frame_sleep_fn=lambda _: None)
    animator.write_frame('LINE1', 'LINE2')
    capsys.readouterr()
    animator.write_frame('LINE1', 'LINE2')
    out = capsys.readouterr().out
    assert 'LINE1' in out
