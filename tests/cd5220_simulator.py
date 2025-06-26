import pytest
from cd5220 import CD5220, DisplayMode


@pytest.fixture
def display():
    return CD5220.create_simulator_only(debug=False)


@pytest.fixture
def display_console(tmp_path):
    disp = CD5220.create_simulator_only(render_console=True, debug=False)
    disp.console_verbose = False
    return disp


@pytest.fixture
def display_console_verbose(tmp_path):
    disp = CD5220.create_simulator_only(render_console=True, debug=False)
    disp.console_verbose = True
    return disp


def test_basic_line_writing(display):
    sim = display.simulator
    display.write_upper_line("HELLO")
    display.write_lower_line("WORLD")
    sim.assert_line_equals(0, "HELLO")
    sim.assert_line_equals(1, "WORLD")


def test_positioned_writing(display):
    sim = display.simulator
    display.write_positioned("X", 5, 2)
    sim.assert_char_at(4, 1, "X")


def test_cursor_moves_and_text(display):
    sim = display.simulator
    display.set_cursor_position(2, 1)
    display.write_at_cursor("A")
    display.cursor_move_right()
    display.write_at_cursor("B")
    sim.assert_char_at(1, 0, "A")
    sim.assert_char_at(3, 0, "B")


def test_cursor_repositioning_sequence(display):
    sim = display.simulator
    display.clear_display()
    display.write_positioned("CURSOR DEMO", 1, 1)
    positions = [(1, 2), (5, 2), (10, 2), (15, 2), (20, 2)]
    for i, (col, row) in enumerate(positions):
        display.set_cursor_position(col, row)
        display.write_at_cursor(str(i + 1))
    expected = "1   2    3    4    5"
    sim.assert_line_equals(1, expected)


def test_clear_and_cancel(display):
    sim = display.simulator
    display.write_positioned("AAAA", 1, 1)
    display.write_positioned("BBBB", 1, 2)
    display.set_cursor_position(1, 2)
    display.cancel_current_line()
    sim.assert_line_equals(0, "AAAA")
    sim.assert_line_equals(1, "")
    display.clear_display()
    sim.assert_line_equals(0, "")
    sim.assert_line_equals(1, "")


def test_viewport_writing(display):
    sim = display.simulator
    display.set_window(1, 5, 10)
    display.enter_viewport_mode()
    display.write_viewport(1, "TEST")
    sim.assert_region_equals(4, 0, 4, "TEST")

def test_viewport_overflow_shows_last_chars(display):
    sim = display.simulator
    display.set_window(1, 4, 10)
    display.enter_viewport_mode()
    display.write_viewport(1, "VIEWPORTTEXT")
    sim.assert_region_equals(3, 0, 7, "ORTTEXT")


def test_display_message_string(display):
    sim = display.simulator
    display.display_message("HELLO WORLD LOWER LINE2", duration=0, mode="string")
    sim.assert_line_contains(0, "HELLO")
    sim.assert_line_contains(1, "NE2")


def test_restore_defaults(display):
    sim = display.simulator
    display.write_upper_line("DATA")
    display.restore_defaults()
    sim.assert_line_equals(0, "")
    sim.assert_line_equals(1, "")


def test_scroll_marquee_parsing(display):
    sim = display.simulator
    display.scroll_marquee("SCROLLING")
    sim.assert_line_contains(0, "SCROLLING"[:20])
    assert sim.scroll_text == "SCROLLING"
    assert sim.current_mode == DisplayMode.SCROLL


def test_window_command_parsing(display):
    sim = display.simulator
    display.set_window(1, 4, 8)
    assert sim.active_window == (1, 4, 8)
    display.clear_window(1)
    assert sim.active_window is None


def test_mode_synchronization(display):
    sim = display.simulator
    display.write_upper_line("MODE")
    assert sim.current_mode == DisplayMode.STRING
    display.clear_display()
    assert sim.current_mode == DisplayMode.NORMAL
    display.set_window(1, 5, 10)
    display.enter_viewport_mode()
    assert sim.current_mode == DisplayMode.VIEWPORT


def test_state_commands(display):
    sim = display.simulator
    display.clear_display()
    display.set_brightness(2)
    display.cursor_on()
    display.display_off()
    display.display_on()
    display.cursor_off()
    sim.assert_brightness(2)
    sim.assert_display_on(True)
    sim.assert_cursor_visible(False)


def test_display_off_frame_blank(display):
    sim = display.simulator
    display.write_both_lines("12345678901234567890", "ABCDEFGHIJKLMNOPQRST")
    display.display_off()
    sim.assert_display_on(False)


def test_complex_sequence(display):
    sim = display.simulator
    display.clear_display()
    display.set_brightness(3)
    display.write_positioned("HELLO", 1, 1)
    display.set_window(2, 5, 10)
    display.enter_viewport_mode()
    display.write_viewport(2, "WORLD")
    display.cancel_current_line()
    display.cursor_on()
    display.display_off()
    display.display_on()
    sim.assert_line_equals(0, "HELLO")
    sim.assert_line_equals(1, "")
    sim.assert_brightness(3)
    sim.assert_display_on(True)
    sim.assert_cursor_visible(True)


def test_console_diffing(display_console, capsys):
    disp = display_console
    disp.write_upper_line("HELLO")
    captured = capsys.readouterr().out
    assert "HELLO" in captured
    disp.set_cursor_position(1, 1)
    output2 = capsys.readouterr().out
    assert "[non-visual]" in output2
    # frame should not be re-rendered
    assert "HELLO" not in output2


def test_non_visual_command_logs(display_console, capsys):
    disp = display_console
    disp.write_upper_line("TEST")
    capsys.readouterr()  # clear

    disp.set_brightness(2)
    out = capsys.readouterr().out
    assert "[non-visual]" in out
    assert "TEST" not in out

    disp.cursor_on()
    out = capsys.readouterr().out
    assert "[non-visual]" in out
    assert "TEST" not in out

    disp.display_off()
    out = capsys.readouterr().out
    assert "[non-visual]" in out
    assert "TEST" not in out


def test_console_verbose_frames(display_console_verbose, capsys):
    disp = display_console_verbose
    disp.write_upper_line("HELLO")
    out1 = capsys.readouterr().out
    assert "HELLO" in out1

    disp.set_brightness(2)
    out2 = capsys.readouterr().out
    assert "[non-visual]" in out2
    assert "--------------------" in out2  # frame re-rendered
