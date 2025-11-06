import pytest
from unittest.mock import Mock, patch
import random
import logging

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


def test_wrapper_additional_methods(mock_display):
    library = ASCIIAnimations(
        mock_display,
        sleep_fn=lambda _: None,
        frame_sleep_fn=lambda _: None,
    )
    library.enable_testing_mode()
    assert isinstance(library.get_simulator(), DisplaySimulator)
    library.play_startup_sequence()
    # typewriter writes each char individually
    assert mock_display.write_positioned.call_count > 0


def test_bounce_multiple_frames(animator):
    bounce(animator, duration=1.3)
    sim = animator.get_simulator()
    assert sim is not None
    combined = sim.get_line(1) + sim.get_line(2)
    assert '*' in combined


def test_fireworks_bursts(animator, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    fireworks(animator, duration=1.5)
    sim = animator.get_simulator()
    assert sim is not None
    combined = sim.get_line(1) + sim.get_line(2)
    assert any(ch != ' ' for ch in combined)


def test_stars_spawn_on_display(animator, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    stars(animator, duration=0.3)
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert any(ch != ' ' for ch in combined)


def test_stars_high_quantity(animator, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    stars(animator, duration=1.0, quantity=40, clustering=1.0, spawn_rate=40)
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 40


def test_stars_integer_quantity(animator, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    stars(animator, duration=1.0, quantity=20, clustering=1.0, spawn_rate=20)
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 20


def _run_spawn_rate(rate, qty=5, frames=5):
    disp = Mock()
    anim = DiffAnimator(
        disp,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        enable_simulator=True,
        frame_rate=1,
    )

    counts = []

    def capture(line1: str, line2: str) -> None:
        counts.append(sum(ch != ' ' for ch in line1 + line2))
        DiffAnimator.write_frame(anim, line1, line2)

    random.seed(0)
    with patch.object(anim, 'write_frame', side_effect=capture):
        stars(
            anim,
            duration=float(frames),
            quantity=qty,
            clustering=1.0,
            spawn_rate=rate,
            full_cycle=1.0,
        )

    return counts


def test_stars_spawn_rate_parameter():
    slow_counts = _run_spawn_rate(1, qty=5, frames=5)
    fast_counts = _run_spawn_rate(5, qty=5, frames=1)
    assert slow_counts == [0, 1, 2, 3, 4, 5]
    assert fast_counts == [0, 5]


def test_stars_spawn_rate_ramp_large():
    counts = _run_spawn_rate(2, qty=19, frames=12)
    assert counts == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 19, 19, 19]


def test_wander_zero_static():
    positions = _capture_wander(0.0, frames=4)
    # After initial spawn positions remain constant
    assert positions[1] == positions[2] == positions[3]


def test_wander_full_relocates():
    positions = _capture_wander(1.0, frames=6)
    unique = {frozenset(p) for p in positions}
    assert len(unique) > 1


def _capture_wander(wander, frames=6):
    disp = Mock()
    anim = DiffAnimator(
        disp,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        enable_simulator=True,
        frame_rate=1,
    )

    positions = []

    def capture(line1: str, line2: str) -> None:
        coords = {
            (x, y)
            for y, line in enumerate([line1, line2])
            for x, ch in enumerate(line)
            if ch != ' '
        }
        positions.append(coords)
        DiffAnimator.write_frame(anim, line1, line2)

    random.seed(0)
    with patch.object(anim, 'write_frame', side_effect=capture):
        stars(
            anim,
            duration=float(frames),
            quantity=5,
            clustering=1.0,
            spawn_rate=5,
            full_cycle=1.0,
            wander=wander,
        )

    return positions


def _run_stars_full(full_cycle, duration=3.0):
    disp = Mock()
    anim = DiffAnimator(
        disp,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        enable_simulator=True,
        frame_rate=1,
    )
    random.seed(0)
    stars(
        anim,
        duration=duration,
        quantity=12,
        clustering=1.0,
        full_cycle=full_cycle,
        spawn_rate=12,
    )
    sim = anim.get_simulator()
    return sim.get_display()


def test_stars_full_cycle_parameter():
    full = _run_stars_full(1.0)
    short = _run_stars_full(0.0)
    mixed = _run_stars_full(0.5)
    assert '*' in full[0] + full[1]
    assert '*' not in short[0] + short[1]
    assert '*' in mixed[0] + mixed[1]


def test_stars_quantity_zero_warns(caplog):
    disp = Mock()
    anim = DiffAnimator(
        disp,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        enable_simulator=True,
        frame_rate=1,
    )
    random.seed(0)
    with caplog.at_level(logging.WARNING):
        stars(anim, duration=1.0, quantity=0, clustering=1.0)
    assert "Quantity 0 is below minimum" in caplog.text


def test_stars_quantity_caps_and_warns(animator, monkeypatch, caplog):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    with caplog.at_level(logging.WARNING):
        stars(animator, duration=1.0, quantity=42, clustering=1.0, spawn_rate=42)
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 40
    assert "Quantity 42 exceeds display capacity" in caplog.text


def test_stars_float_quantity_rounds_down(animator, caplog, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    with caplog.at_level(logging.WARNING):
        stars(animator, duration=1.0, quantity=5.7, clustering=1.0, spawn_rate=6)
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 5
    assert "Quantity 5.7 rounded down to 5" in caplog.text


def test_stars_negative_quantity_warns(animator, caplog, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    with caplog.at_level(logging.WARNING):
        stars(animator, duration=1.0, quantity=-3, clustering=1.0)
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 1
    assert "Quantity -3 is below minimum" in caplog.text


def test_clustering_caps_quantity_warns(animator, caplog, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    with caplog.at_level(logging.WARNING):
        stars(animator, duration=1.0, quantity=25, clustering=0.0, spawn_rate=25)
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 20
    assert "may only fit 20 stars" in caplog.text


def test_spawn_rate_caps_and_warns(animator, caplog, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    with caplog.at_level(logging.WARNING):
        stars(
            animator,
            duration=1.0,
            quantity=5,
            clustering=1.0,
            spawn_rate=10,
        )
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 5
    assert "Spawn rate 10 exceeds quantity" in caplog.text


def test_spawn_rate_zero_warns(animator, caplog, monkeypatch):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    with caplog.at_level(logging.WARNING):
        stars(
            animator,
            duration=0.25,
            quantity=5,
            clustering=1.0,
            spawn_rate=0,
        )
    sim = animator.get_simulator()
    combined = sim.get_line(1) + sim.get_line(2)
    assert sum(ch != ' ' for ch in combined) == 1
    assert "Spawn rate 0 is below minimum" in caplog.text


def test_stars_logging_includes_validated_values(monkeypatch, caplog):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    disp = Mock()
    anim = DiffAnimator(
        disp,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
        enable_simulator=True,
    )
    with caplog.at_level(logging.INFO):
        stars(anim, duration=0.25, quantity=7.8, spawn_rate=3)
    assert "Starting stars animation" in caplog.text
    assert "quantity=7" in caplog.text
    assert "Quantity 7.8 rounded down to 7" in caplog.text


def test_wander_validation(monkeypatch, caplog):
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    with caplog.at_level(logging.WARNING):
        stars(DiffAnimator(Mock(), sleep_fn=lambda _ : None,
                           frame_sleep_fn=lambda _ : None,
                           enable_simulator=True),
              duration=0.25, quantity=5, wander=2.0)
    assert "Wander 2.0 exceeds 1.0" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        stars(DiffAnimator(Mock(), sleep_fn=lambda _ : None,
                           frame_sleep_fn=lambda _ : None,
                           enable_simulator=True),
              duration=0.25, quantity=5, wander=-0.5)
    assert "Wander -0.5 is below minimum" in caplog.text
