"""Collection of built-in ASCII animations."""
import random
import time
from typing import List, Iterator, Tuple, Optional, Union

from cd5220 import DiffAnimator, DisplaySimulator
import logging
import math

logger = logging.getLogger('CD5220_Animations')


def _log_animation_start(name: str, **kwargs: object) -> None:
    """Log the parameters an animation will run with."""
    params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info("Starting %s animation with %s", name, params)

STAR_PHASES = ['.', '+', '*', '+', '.']
def bounce(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Bouncing ball with gravity effect."""
    _log_animation_start('bounce', duration=duration)
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
    _log_animation_start('progress', duration=duration)
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

    if duration is None:
        while True:
            run_once()
    else:
        run_once()


def loader(animator: DiffAnimator, duration: Optional[float] = None) -> None:
    """Spinner animation updating only the spinner character."""
    _log_animation_start('loader', duration=duration)
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
    _log_animation_start('matrix', duration=duration)
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
    _log_animation_start('typewriter', text=text, line=line)
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
    _log_animation_start('alert', message=message, duration=duration)
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
    _log_animation_start('tapestry', duration=duration)
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
    _log_animation_start('clouds', duration=duration)
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
    _log_animation_start(
        'zen',
        duration=duration,
        max_radius=max_radius,
        phase_offset=phase_offset,
        pause_length=pause_length,
    )
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
    _log_animation_start('fireworks', duration=duration)
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
    quantity: Union[int, float] = 5,
    clustering: float = 0.3,
    full_cycle: float = 0.7,
    spawn_rate: int = 1,
    wander: float = 0.0,
) -> None:
    """Twinkling starfield with adjustable density.

    Defaults are ``quantity=5``, ``clustering=0.3``, ``full_cycle=0.7`` and
    ``spawn_rate=1``.

    ``quantity`` is the desired number of concurrently visible stars. Values
    below ``1`` are invalid and will be replaced with ``1``. Values above ``40``
    are capped at ``40``. Non-integer values are rounded down with a warning.

    ``clustering`` controls how likely new stars appear next to existing ones.
    ``0`` prevents adjacent placement entirely while ``1`` always chooses a
    neighboring position when available.


    ``full_cycle`` controls the probability that a newly spawned star will
    twinkle. ``0`` results in static ``'.'`` characters while ``1`` forces every
    star to cycle through all phases repeatedly. Values between ``0`` and ``1``
    mix these behaviors.

    ``spawn_rate`` sets how many new stars may appear in a single frame. The
    default of ``1`` staggers stars so their phases do not align. Values below
    ``1`` are replaced with ``1`` and values above ``quantity`` are capped with a
    warning.

    ``wander`` controls how likely stars relocate when their cycle completes.
    ``0`` keeps them fixed in place while ``1`` causes a full reshuffle every
    cycle. Intermediate values blend these behaviors.

    Large quantities combined with low ``clustering`` may not fit on the
    display. In that case the quantity is capped using an estimated capacity and
    a warning is logged.

    Stars start at random phases when ``full_cycle`` is non-zero so the field
    twinkles independently once populated.
    """



    total_cells = 40
    orig_quantity = quantity

    orig_spawn = spawn_rate
    orig_wander = wander

    if isinstance(quantity, float) and not quantity.is_integer():
        if quantity >= 1:
            logger.warning(
                "Quantity %s rounded down to %d",
                orig_quantity,
                math.floor(quantity),
            )
        quantity = math.floor(quantity)

    quantity = int(quantity)

    if quantity < 1:
        logger.warning(
            "Quantity %s is below minimum; using 1 instead",
            orig_quantity,
        )
        quantity = 1
    elif quantity > total_cells:
        logger.warning(
            "Quantity %s exceeds display capacity; capping at %d",
            orig_quantity,
            total_cells,
        )
        quantity = total_cells

    expected_capacity = int(20 + 20 * clustering)
    if quantity > expected_capacity:
        logger.warning(
            "Quantity %s with clustering %.1f may only fit %d stars",
            orig_quantity,
            clustering,
            expected_capacity,
        )
        quantity = expected_capacity

    if spawn_rate < 1:
        logger.warning(
            "Spawn rate %s is below minimum; using 1 instead",
            orig_spawn,
        )
        spawn_rate = 1
    elif spawn_rate > quantity:
        logger.warning(
            "Spawn rate %s exceeds quantity; capping at %d",
            orig_spawn,
            quantity,
        )
        spawn_rate = quantity

    if wander < 0.0:
        logger.warning(
            "Wander %s is below minimum; using 0.0 instead",
            orig_wander,
        )
        wander = 0.0
    elif wander > 1.0:
        logger.warning(
            "Wander %s exceeds 1.0; capping at 1.0",
            orig_wander,
        )
        wander = 1.0

    _log_animation_start(
        'stars',
        duration=duration,
        quantity=quantity,
        clustering=clustering,
        full_cycle=full_cycle,
        spawn_rate=spawn_rate,
        wander=wander,
    )

    _run_stars(
        animator,
        duration,
        quantity,
        clustering,
        full_cycle,
        spawn_rate,
        wander,
    )


def _run_stars(
    animator: DiffAnimator,
    duration: Optional[float],
    quantity: int,
    clustering: float,
    full_cycle: float,
    spawn_rate: int,
    wander: float,
) -> None:
    frame_count = max(1, int(duration * animator.frame_rate)) if duration else None
    active: List[dict] = []
    frame = 0
    animator.write_frame(' ' * 20, ' ' * 20)

    max_active = max(1, min(quantity, 40))
    # limit how many stars spawn in a single frame so phases become staggered
    max_spawn_per_frame = max(1, min(spawn_rate, max_active))

    def has_neighbor(x: int, y: int) -> bool:
        return any(abs(s['x'] - x) + abs(s['y'] - y) == 1 for s in active)

    def conflicts(x: int, y: int) -> bool:
        if any(s['x'] == x and s['y'] == y for s in active):
            return True
        if clustering == 0.0 and has_neighbor(x, y):
            return True
        return False

    while frame_count is None or frame < frame_count:

        removed = 0
        for star in list(active):
            star['phase'] = (star['phase'] + 1) % len(STAR_PHASES)
            cycle_reset = star['phase'] == 0
            if (
                not star.get('full', True)
                or (cycle_reset and random.random() < wander)
            ):
                active.remove(star)
                removed += 1

        open_slots = [
            (x, y)
            for y in range(2)
            for x in range(20)
            if not conflicts(x, y)
        ]
        random.shuffle(open_slots)
        if len(active) < max_active:
            spawn_budget = min(max_spawn_per_frame, max_active - len(active))
        else:
            spawn_budget = removed
        neighbor_slots = [s for s in open_slots if has_neighbor(*s)]
        empty_slots = [s for s in open_slots if s not in neighbor_slots]
        for _ in range(spawn_budget):
            pool: List[Tuple[int, int]]
            if clustering == 0.0:
                if not empty_slots:
                    break
                pool = empty_slots
            elif clustering == 1.0 and neighbor_slots:
                pool = neighbor_slots
            else:
                if neighbor_slots and random.random() < clustering:
                    pool = neighbor_slots
                elif empty_slots:
                    pool = empty_slots
                elif neighbor_slots:
                    pool = neighbor_slots
                else:
                    break
            x, y = pool.pop()
            if pool is neighbor_slots and (x, y) in empty_slots:
                empty_slots.remove((x, y))
            elif pool is empty_slots and (x, y) in neighbor_slots:
                neighbor_slots.remove((x, y))
            prob = max(0.0, min(1.0, full_cycle))
            full = random.random() < prob
            phase_start = 0 if len(active) < max_active else (
                random.randint(0, len(STAR_PHASES) - 1) if full else 0
            )
            active.append({'x': x, 'y': y, 'phase': phase_start, 'full': full})
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
        quantity: Union[int, float] = 5,
        clustering: float = 0.3,
        full_cycle: float = 0.7,
        spawn_rate: int = 1,
        wander: float = 0.0,
    ) -> None:
        stars(
            self.animator,
            duration,
            quantity,
            clustering,
            full_cycle,
            spawn_rate,
            wander,
        )

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
