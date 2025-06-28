"""Collection of built-in ASCII animations."""
import random
import time
from typing import List, Iterator, Tuple, Optional, Union
from enum import Enum

from cd5220 import DiffAnimator, DisplaySimulator

STAR_PHASES = ['.', '+', '*', '+', '.']


class StarMode(Enum):
    """Available star animation modes."""

    NORMAL = "normal"           # Random twinkling
    CASCADE = "cascade"         # Falling stars



def bounce(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Bouncing ball with gravity effect."""
    ball_x, ball_y = 0, 0
    vel_x, vel_y = 1, 1
    frame_count = max(1, int(duration * animator.frame_rate)) if duration else None

    def build_frame() -> Tuple[str, str]:
        line1 = [" "] * 20
        line2 = ["_"] * 20
        if ball_y == 0:
            line1[ball_x] = "*"
        else:
            line2[ball_x] = "*"
        return "".join(line1), "".join(line2)

    line1, line2 = build_frame()
    animator.write_frame(line1, line2)

    i = 0
    while frame_count is None or i < frame_count:
        ball_x += vel_x
        ball_y += vel_y

        if ball_x <= 0 or ball_x >= 19:
            vel_x = -vel_x
            ball_x = max(0, min(ball_x, 19))
        if ball_y <= 0 or ball_y >= 1:
            vel_y = -vel_y
            ball_y = max(0, min(ball_y, 1))

        line1, line2 = build_frame()
        animator.write_frame(line1, line2)

        if ball_y == 0:
            animator.frame_sleep(1.2 / animator.frame_rate)
        else:
            animator.frame_sleep(0.8 / animator.frame_rate)
        i += 1


def progress(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Animated progress bar using write_frame for each step."""
    steps = 10
    step_duration = duration / steps if duration else 1.0 / animator.frame_rate

    base_line1 = "LOADING    %        "
    base_line2 = "    [          ]    "
    animator.write_frame(base_line1, base_line2)

    def run_once() -> None:
        for step in range(steps + 1):
            percent = step / steps
            filled = int(percent * 10)
            percentage = f"{int(percent * 100):03d}"

            line1_chars = list(base_line1)
            for i, ch in enumerate(percentage):
                line1_chars[8 + i] = ch
            line2_chars = list(base_line2)
            for i in range(10):
                line2_chars[5 + i] = '=' if i < filled else ' '

            animator.write_frame(''.join(line1_chars), ''.join(line2_chars))
            animator.frame_sleep(step_duration)

        animator.write_frame('     COMPLETE!      ', '    [==========]    ')

    if duration is None:  # pragma: no cover - infinite loop for manual demo
        while True:
            run_once()
    else:
        run_once()


def loader(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Spinner animation updating only the spinner character."""
    spinner_chars = ['|', '/', '-', '\\']
    frame_count = int(duration * animator.frame_rate) if duration else None

    base_text = "   Processing  "
    line1_base = base_text.ljust(20)
    line2 = "   Please wait...   "

    spinner_col = len(base_text)
    animator.write_frame(line1_base, line2)

    frame = 0
    while frame_count is None or frame < frame_count:
        chars = list(line1_base)
        chars[spinner_col] = spinner_chars[frame % len(spinner_chars)]
        animator.write_frame(''.join(chars), line2)
        animator.frame_sleep(1.0 / animator.frame_rate)
        frame += 1

    animator.write_frame(line1_base, line2)


def matrix(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    columns = []
    for _ in range(20):
        columns.append({'chars': [], 'next_spawn': random.randint(0, 10)})

    frame_count = int(duration * animator.frame_rate) if duration else None
    chars = '01ABCDEF'

    animator.write_frame(' ' * 20, ' ' * 20)

    frame = 0
    while frame_count is None or frame < frame_count:
        line1_chars = [' '] * 20
        line2_chars = [' '] * 20
        for col_idx, column in enumerate(columns):
            if column['next_spawn'] <= 0:
                column['chars'].append({'char': random.choice(chars), 'y': -1})
                column['next_spawn'] = random.randint(3, 8)
            column['next_spawn'] -= 1

            for char_data in column['chars'][:]:
                char_data['y'] += 1
                if char_data['y'] >= 2:
                    column['chars'].remove(char_data)
                elif char_data['y'] == 0:
                    line1_chars[col_idx] = char_data['char']
                elif char_data['y'] == 1:
                    line2_chars[col_idx] = char_data['char']
        animator.write_frame(''.join(line1_chars), ''.join(line2_chars))
        animator.frame_sleep(1.0 / animator.frame_rate)
        frame += 1


def typewriter(animator: DiffAnimator, text: str, line: int = 0) -> None:
    row = 0 if line == 0 else 1
    for i, ch in enumerate(text):
        animator.display.write_positioned(ch, i + 1, row + 1)
        animator.sleep(0.1)

    cursor_col = len(text) + 1
    for blink in range(6):
        cursor = '_' if blink % 2 == 0 else ' '
        animator.display.write_positioned(cursor, cursor_col, row + 1)
        animator.frame_sleep(0.3)


def alert(animator: DiffAnimator, message: str, duration: Optional[float] = None) -> None:
    """Pulse brightness while keeping text static."""
    pulse_count = int(duration * 2) if duration else None
    centered = message.center(20)
    animator.write_frame(centered, centered)
    pulse = 0
    while pulse_count is None or pulse < pulse_count:
        brightness = 4 if pulse % 2 == 0 else 1
        animator.display.set_brightness(brightness)
        animator.frame_sleep(0.5)
        pulse += 1
    animator.display.set_brightness(4)


def tapestry(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Field of spinners rotating in place."""
    spinner_chars = ['|', '/', '-', '\\']
    frame_count = int(duration * animator.frame_rate) if duration else None

    row1 = "X X X X X X X X X X".ljust(20)
    row2 = " X X X X X X X X X X".ljust(20)

    row1_positions = []
    row2_positions = []

    for i, char in enumerate(row1):
        if char.upper() == 'X':
            row1_positions.append(i)

    for i, char in enumerate(row2):
        if char.upper() == 'X':
            row2_positions.append(i)

    def build_frame(frame: int) -> Tuple[str, str]:
        line1 = [' '] * 20
        line2 = [' '] * 20

        for col_idx, pos in enumerate(row1_positions):
            idx = (frame + col_idx) % 4
            line1[pos] = spinner_chars[idx]

        for col_idx, pos in enumerate(row2_positions):
            idx = (frame + col_idx) % 4
            line2[pos] = spinner_chars[(idx + 2) % 4]

        return "".join(line1), "".join(line2)

    line1, line2 = build_frame(0)
    animator.write_frame(line1, line2)
    f = 0
    while frame_count is None or f < frame_count:
        line1, line2 = build_frame(f + 1)
        animator.write_frame(line1, line2)
        animator.frame_sleep(1.0 / animator.frame_rate)
        f += 1


def clouds(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Drifting clouds that occasionally merge as they pass."""
    # Clouds move at independent speeds. When two clouds are adjacent or one
    # space apart they combine into a single wider cloud. Each cloud randomly
    # chooses ``()`` or ``{}`` as its boundary characters and keeps that style
    # while moving across the screen.
    frame_count = int(duration * animator.frame_rate) if duration else None

    def seed_clouds() -> List[dict]:
        """Create three clouds with random starting positions and speeds."""
        clouds = []
        while len(clouds) < 3:
            x = random.randint(0, 17)
            if all(abs(x - c['x']) > 3 for c in clouds):
                clouds.append(
                    {
                        'x': x,
                        'speed': random.choice([1, 2]),
                        'delay': 0,
                        'pair': random.choice(['()', '{}']),
                    }
                )
        return sorted(clouds, key=lambda c: c['x'])

    clouds_top = seed_clouds()
    clouds_bot = seed_clouds()

    def move_clouds(clouds_line: List[dict]) -> None:
        for c in clouds_line:
            if c['delay'] == 0:
                new_x = c['x'] - 1
                if new_x < -2:
                    # wrap and respawn with new speed and style
                    c['x'] = 17
                    c['speed'] = random.choice([1, 2])
                    c['pair'] = random.choice(['()', '{}'])
                else:
                    c['x'] = new_x
                c['delay'] = c['speed'] - 1
            else:
                c['delay'] -= 1

    def render_line(clouds_line: List[dict]) -> str:
        line = [' '] * 20
        clouds_sorted = sorted(clouds_line, key=lambda c: c['x'])
        segments: List[dict] = []
        for c in clouds_sorted:
            start = c['x']
            end = start + 2
            if not segments or start > segments[-1]['end'] + 2:
                segments.append({'start': start, 'end': end, 'pair': c['pair']})
            else:
                seg = segments[-1]
                seg['end'] = max(seg['end'], end)

        for seg in segments:
            start, end = seg['start'], seg['end']
            width = end - start + 1
            pair = seg['pair']
            for i in range(width):
                pos = start + i
                if 0 <= pos < 20:
                    if i == 0:
                        line[pos] = pair[0]
                    elif i == width - 1:
                        line[pos] = pair[1]
                    else:
                        line[pos] = '~'
        return ''.join(line)

    def render() -> Tuple[str, str]:
        return render_line(clouds_top), render_line(clouds_bot)

    line1, line2 = render()
    animator.write_frame(line1, line2)
    frame = 0
    while frame_count is None or frame < frame_count:
        move_clouds(clouds_top)
        move_clouds(clouds_bot)
        line1, line2 = render()
        animator.write_frame(line1, line2)
        animator.frame_sleep(1.0 / animator.frame_rate)
        frame += 1


def zen(
    animator: DiffAnimator,
    duration: Optional[float] = None,
    max_radius: int = 10,
    phase_offset: int = 3,
    pause_length: int = 10,
) -> None:
    """Calming dot that expands and contracts in a breathing rhythm."""
    frame_count = int(duration * animator.frame_rate) if duration else None
    width = 20
    center = width // 2
    max_radius = min(max_radius, center - 1)

    def build_line(radius: int) -> str:
        if radius == 0:
            line = [' '] * width
            line[center] = '.'
            return ''.join(line)

        line = [' '] * width
        for i in range(width):
            dist = abs(i - center)
            if dist == radius:
                line[i] = '.'
            elif dist == radius - 1:
                line[i] = 'o'
            elif dist < radius:
                line[i] = 'O'
        return ''.join(line)

    cycle_length = 2 * max_radius + pause_length

    def get_radius(frame: int) -> int:
        frame_offset = frame + pause_length
        frame_mod = frame_offset % cycle_length

        if frame_mod < pause_length:
            return 0
        elif frame_mod < pause_length + max_radius:
            return (frame_mod - pause_length) + 1
        else:
            return max_radius - ((frame_mod - pause_length) - max_radius)

    rest_line = build_line(0)
    animator.write_frame(rest_line, rest_line)

    i = 0
    while frame_count is None or i < frame_count:
        radius1 = get_radius(i)
        radius2 = get_radius(i + phase_offset)
        line1 = build_line(radius1)
        line2 = build_line(radius2)
        animator.write_frame(line1, line2)
        animator.frame_sleep(1.0 / animator.frame_rate)
        i += 1


def fireworks(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Randomized star bursts with expanding rings."""
    frame_count = int(duration * animator.frame_rate) if duration else None
    bursts: List[Tuple[int, Tuple[int, int]]] = []

    def render(f: int) -> Tuple[str, str]:
        line1 = [' '] * 20
        line2 = [' '] * 20
        for start, (x, y) in bursts:
            t = f - start
            if t < 0 or t > 9:
                continue
            if t == 0:
                if y == 0:
                    line1[x] = '*'
                else:
                    line2[x] = '*'
            else:
                radius = t
                left = x - radius
                right = x + radius
                if y == 0:
                    if 0 <= left < 20:
                        line1[left] = '('
                    if 0 <= right < 20:
                        line1[right] = ')'
                else:
                    if 0 <= left < 20:
                        line2[left] = '('
                    if 0 <= right < 20:
                        line2[right] = ')'
        return "".join(line1), "".join(line2)

    f = 0
    while frame_count is None or f < frame_count:
        if random.random() < 0.1:
            bursts.append((f, (random.randint(3, 16), random.randint(0, 1))))

        line1, line2 = render(f)
        animator.write_frame(line1, line2)
        animator.frame_sleep(1.0 / animator.frame_rate)
        f += 1


def stars(
    animator: DiffAnimator,
    duration: Optional[float] = None,
    quantity: float = 0.3,
    clustering: float = 0.0,
    mode: Union[str, StarMode, List[Union[str, StarMode]]] = StarMode.NORMAL,
) -> None:
    """Twinkling starfield with adjustable density.

    ``quantity`` controls the fraction of active cells. ``clustering`` is the
    inverse of the old ``sparseness`` parameter: ``0`` forces wide spacing while
    ``1`` allows stars to appear right next to each other. ``mode`` selects one
    of two behaviors:

    - ``NORMAL`` - random twinkling across both rows
    - ``CASCADE`` - stars spawn on the top row and fall to the bottom

    When multiple modes are supplied as a comma-separated list, each runs for
    ``duration / len(modes)`` seconds in sequence. ``duration`` must be provided
    when using multiple modes.
    """

    def parse_mode(val: Union[str, StarMode]) -> StarMode:
        if isinstance(val, StarMode):
            return val
        return StarMode(val.lower())

    if isinstance(mode, list):
        modes = [parse_mode(m) for m in mode]
    elif isinstance(mode, StarMode):
        modes = [mode]
    else:
        mode_str = str(mode)
        modes = [parse_mode(m.strip()) for m in mode_str.split(',') if m.strip()]

    if len(modes) > 1 and duration is None:
        raise ValueError("Duration is required when multiple modes are specified")

    per_duration = None if duration is None else duration / len(modes)

    for single_mode in modes:
        _run_stars_mode(animator, per_duration, quantity, clustering, single_mode)
        if duration is None:
            break


def _run_stars_mode(
    animator: DiffAnimator,
    duration: Optional[float],
    quantity: float,
    clustering: float,
    mode: StarMode,
) -> None:
    frame_count = max(1, int(duration * animator.frame_rate)) if duration else None
    active: List[dict] = []
    frame = 0
    animator.write_frame(' ' * 20, ' ' * 20)

    def scaled_quantity(q: float) -> float:
        """Map ``quantity`` to a more exponential curve.

        This polynomial is fit so that ``quantity`` of 0.1, 0.5, 0.8 and 1.0
        correspond to roughly 2, 11, 33 and 35 active stars respectively.
        """
        q = max(0.0, min(1.0, q))
        return (
            -7.648809523809524 * q ** 4
            + 12.821428571428571 * q ** 3
            - 5.19672619047619 * q ** 2
            + 0.8991071428571429 * q
        )

    max_active = max(1, int(round(40 * scaled_quantity(quantity))))
    # ``clustering`` is the inverse of the old ``sparseness`` parameter.
    # ``0`` means maximum spacing and prohibits vertically adjacent stars,
    # ``1`` favors grouping. The gap decreases as clustering increases.
    min_gap = round((1 - clustering) * 2)
    # limit how many stars spawn in a single frame so phases become staggered
    max_spawn_per_frame = max(1, max_active)

    def conflicts(x: int, y: int) -> bool:
        for s in active:
            if s['y'] == y and abs(s['x'] - x) <= min_gap:
                return True
            if clustering == 0.0 and s['x'] == x and s['y'] != y:
                return True
        return False

    def spawn_chance(dist: int) -> float:
        """Return probability of spawning at a given distance."""
        if dist <= 2:
            return 1.0
        return max(0.1, 1.0 - clustering * (dist - 2) / 3)

    while frame_count is None or frame < frame_count:

        for star in list(active):
            star['phase'] += 1
            if mode == StarMode.CASCADE:
                star['y'] += 1
            if star['phase'] >= len(STAR_PHASES) or star['y'] >= 2:
                active.remove(star)

        if mode == StarMode.CASCADE:
            open_slots = [(x, 0) for x in range(20)]
        else:
            open_slots = [(x, y) for y in range(2) for x in range(20)]
        random.shuffle(open_slots)
        spawn_budget = min(max_spawn_per_frame, max_active - len(active))
        spawned: List[Tuple[int, int]] = []
        for x, y in open_slots:
            if spawn_budget <= 0:
                break
            if conflicts(x, y):
                continue
            if clustering > 0:
                if active:
                    dist = min(abs(s['x'] - x) + abs(s['y'] - y) for s in active)
                    if random.random() > spawn_chance(dist):
                        continue
                if clustering < 0.5 and any(abs(px - x) <= 1 and py == y for px, py in spawned):
                    continue
            active.append({'x': x, 'y': y, 'phase': random.randint(0, len(STAR_PHASES) - 1)})
            spawned.append((x, y))
            spawn_budget -= 1

        line1 = [' '] * 20
        line2 = [' '] * 20

        for star in active:
            char = STAR_PHASES[star['phase']]
            if star['y'] == 0:
                line1[star['x']] = char
            else:
                line2[star['x']] = char

        animator.write_frame(''.join(line1), ''.join(line2))
        animator.frame_sleep(1.0 / animator.frame_rate)
        frame += 1


class ASCIIAnimations:
    """High level ASCII animation wrapper."""

    def __init__(
        self,
        display: 'cd5220.CD5220',
        frame_rate: float = 4,
        sleep_fn: callable = time.sleep,
        frame_sleep_fn: callable = time.sleep,
        render_console: bool = False,
    ) -> None:
        self.display = display
        self.animator = DiffAnimator(
            display,
            frame_rate=frame_rate,
            sleep_fn=sleep_fn,
            frame_sleep_fn=frame_sleep_fn,
            render_console=render_console,
        )
        self.animator.reset_tracking()

    def bounce(self, duration: float = 10.0) -> None:
        bounce(self.animator, duration)

    def progress(self, duration: float = 8.0) -> None:
        progress(self.animator, duration)

    def loader(self, duration: float = 6.0) -> None:
        loader(self.animator, duration)

    def matrix(self, duration: float = 12.0) -> None:
        matrix(self.animator, duration)

    def typewriter(self, text: str, line: int = 0) -> None:
        typewriter(self.animator, text, line)

    def alert(self, message: str, duration: float = 6.0) -> None:
        alert(self.animator, message, duration)

    def tapestry(self, duration: float = 6.0) -> None:
        tapestry(self.animator, duration)

    def clouds(self, duration: float = 6.0) -> None:
        clouds(self.animator, duration)

    def zen(
        self,
        duration: float = 7.5,
        max_radius: int = 10,
        phase_offset: int = 3,
        pause_length: int = 10,
    ) -> None:
        zen(self.animator, duration, max_radius, phase_offset, pause_length)

    def fireworks(self, duration: float = 6.0) -> None:
        fireworks(self.animator, duration)

    def stars(
        self,
        duration: float = 10.0,
        quantity: float = 0.3,
        clustering: float = 0.0,
        mode: Union[str, StarMode, List[Union[str, StarMode]]] = StarMode.NORMAL,
    ) -> None:
        stars(self.animator, duration, quantity, clustering, mode)

    def get_simulator(self) -> Optional[DisplaySimulator]:
        return self.animator.simulator

    def enable_testing_mode(self) -> None:
        self.animator.enable_testing_mode()

    def play_startup_sequence(self) -> None:
        self.typewriter("ASCII ANIMATE DEMO", line=0)
        self.animator.frame_sleep(1)
        self.animator.clear_display()

    def play_demo_cycle(self) -> None:  # pragma: no cover - demo helper
        animations = [
            ("Bounce", lambda: self.bounce(duration=10)),
            ("Matrix", lambda: self.matrix(duration=10)),
            ("Loader", lambda: self.loader(duration=5)),
            ("Progress", lambda: self.progress(duration=5)),
            ("Tapestry", lambda: self.tapestry(duration=10)),
            ("Clouds", lambda: self.clouds(duration=10)),
            ("Zen", lambda: self.zen(30)),
            ("Fireworks", lambda: self.fireworks(20)),
            ("Stars", lambda: self.stars(20)),
        ]
        for name, func in animations:
            self.animator.clear_display()
            self.typewriter(name, line=0)
            self.animator.frame_sleep(1)
            self.animator.clear_display()
            func()
            self.animator.frame_sleep(1)

    def play_error_alert(self, error_message: str) -> None:  # pragma: no cover - demo helper
        for flash in range(6):
            if flash % 2 == 0:
                border = '*' * 20
                self.display.write_both_lines(border, border)
            else:
                centered = error_message[:18].center(20)
                self.display.write_both_lines(centered, ' ' * 20)
            self.animator.frame_sleep(0.3)
        self.alert(error_message[:20], duration=3)


ANIMATIONS = {
    'bounce': bounce,
    'progress': progress,
    'loader': loader,
    'matrix': matrix,
    'typewriter': typewriter,
    'alert': alert,
    'tapestry': tapestry,
    'clouds': clouds,
    'zen': zen,
    'fireworks': fireworks,
    'stars': stars,
}
