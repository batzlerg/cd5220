import pytest
from unittest.mock import Mock, patch
import random

from cd5220 import DiffAnimator, CD5220, DisplaySimulator
from animations import (
    bounce,
    progress,
    loader,
    matrix,
    tapestry,
    clouds,
    zen,
    fireworks,
    stars,
    typewriter,
    alert,
    ASCIIAnimations,
    StarMode,
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
    bounce(animator, duration=0.3)
    progress(animator, duration=0.3)
    loader(animator, duration=0.3)
    matrix(animator, duration=0.3)
    tapestry(animator, duration=0.3)
    clouds(animator, duration=0.3)
    zen(animator, duration=0.3)
    fireworks(animator, duration=0.3)
    stars(animator, duration=0.3)
    assert animator.display.write_positioned.called
    assert not animator.display.write_both_lines.called


def test_typewriter_and_pulse_use_display(animator):
    typewriter(animator, 'TEST', line=0)
    alert(animator, 'ALERT', duration=0.2)
    assert animator.display.write_positioned.called
    assert not animator.display.write_both_lines.called
    assert animator.display.set_brightness.called


def test_wrapper_instantiation(mock_display):
    library = ASCIIAnimations(
        mock_display,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        render_console=False,
    )
    assert library.display is mock_display
    assert isinstance(library.animator, DiffAnimator)


def test_wrapper_methods_execute(mock_display):
    library = ASCIIAnimations(
        mock_display,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
    )
    library.bounce(duration=0.3)
    library.progress(duration=0.3)
    library.loader(duration=0.3)
    library.matrix(duration=0.3)
    library.tapestry(duration=0.3)
    library.clouds(duration=0.3)
    library.zen(duration=0.3)
    library.fireworks(duration=0.3)
    library.stars(duration=0.3)
    assert mock_display.write_positioned.called

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
    bounce(animator, duration=0.5)
    assert frame_calls


def test_spinning_loader_updates_spinner_only(animator):
    loader(animator, duration=0.3)
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
            progress(animator, duration=0.3)
            assert not wb.called
            assert cd.call_count == 0


def test_display_simulator_diff():
    sim = DisplaySimulator()
    sim.apply_frame("HELLO", "WORLD")
    changes = list(sim.diff(["HELLO", "THERE"]))
    assert (1, 2, 'T') in changes


def test_progress_bar_static_elements(animator):
    progress(animator, duration=0.3)
    sim = animator.simulator
    assert sim is not None
    sim.assert_char_at(5, 2, '[')
    sim.assert_char_at(16, 2, ']')


def test_simulator_assertions_and_access(mock_display):
    animator = DiffAnimator(mock_display, enable_simulator=False,
                            sleep_fn=lambda _: None, frame_sleep_fn=lambda _: None)
    assert animator.get_simulator() is None
    animator.enable_testing_mode()
    sim = animator.get_simulator()
    assert isinstance(sim, DisplaySimulator)
    progress(animator, duration=0.3)
    sim.assert_line_contains(1, "COMPLETE")
    sim.assert_line_equals(2, "    [==========]    ")
    sim.assert_static_preserved([(5, 2, '['), (16, 2, ']')])
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


def test_stars_spawn_on_display(animator, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    stars(animator, duration=0.3)
    sim = animator.get_simulator()
    assert sim is not None
    combined = sim.get_line(1) + sim.get_line(2)
    assert any(ch != ' ' for ch in combined)


def test_stars_high_quantity(animator, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    stars(animator, duration=1.0, quantity=1.0, clustering=1.0)
    sim = animator.get_simulator()
    assert sim is not None
    combined = sim.get_line(1) + sim.get_line(2)
    active_count = sum(ch != ' ' for ch in combined)
    assert active_count >= 35


def _run_stars(mode, duration=2.0, qty=0.3, cluster=1.0):
    from animations import stars, StarMode
    from cd5220 import DiffAnimator
    disp = Mock()
    anim = DiffAnimator(disp, sleep_fn=lambda _ : None,
                        frame_sleep_fn=lambda _ : None,
                        enable_simulator=True, frame_rate=1)
    random.seed(0)
    stars(anim, duration=duration, quantity=qty, clustering=cluster, mode=mode)
    sim = anim.get_simulator()
    return sim.get_display()


def test_star_modes_distinct():
    normal = _run_stars(StarMode.NORMAL)
    cascade = _run_stars(StarMode.CASCADE)
    assert normal != cascade
    assert normal == ('.+             .    ', '                    ')
    assert cascade == ('                    ', '          +     + + ')


