# Animation Development Guide

This document outlines the recommended process for creating new ASCII animations for the CD5220 display library. Animations rely on the `DiffAnimator` class which updates the hardware efficiently using batched differential writes and can be paired with `DisplaySimulator` for testing.

## Performance Architecture

The `DiffAnimator` class uses an optimized **batched diff** rendering approach:

- **Differential updates**: Only characters that changed since the last frame are transmitted to the display
- **Batched writes**: Contiguous runs of changed characters are grouped into single write operations
- **Serial efficiency**: Reduces transmission overhead by 65-70% compared to character-by-character updates

This architecture achieves smooth animation at 6-10 FPS on hardware, with higher frame rates possible for sparse animations (minimal screen changes per frame).

### Hardware Constraints

The CD5220 communicates over RS-232 serial at 9600 baud (960 bytes/sec theoretical). At this rate:
- Full 40-character screen update: ~200 bytes = 208ms minimum
- Typical scrolling animation: ~30 bytes/frame = 31ms transmission time
- Maximum sustained rate: ~6 FPS for moderate animations, 10+ FPS for sparse updates

Design animations with these constraints in mind. Sparse animations (moving a single character or small pattern) perform better than full-screen effects.

## 1. Plan the Animation

- Sketch the static portions of both display lines (20 characters each).
- Decide which characters will change each frame.
- Determine the desired frame rate and total duration.
- Consider change density: animations updating <30% of the screen per frame perform best.

## 2. Write the Animation Function

```
from cd5220 import DiffAnimator

def custom_animation(animator: DiffAnimator, duration: float = 5.0) -> None:
frame_count = int(duration * animator.frame_rate)
base_line1 = "YOUR STATIC TEXT".ljust(20)
base_line2 = "SECOND LINE".ljust(20)
animator.write_frame(base_line1, base_line2)

    for frame in range(frame_count):
        # build updated lines here based on `frame`
        animator.write_frame(updated_line1, updated_line2)
        animator.frame_sleep(1.0 / animator.frame_rate)
 ```

### How `write_frame()` Works

`write_frame()` accepts two 20-character strings (one per display row) and:

1. **Compares** the new frame against the previous frame buffer
2. **Identifies** contiguous runs of changed characters
3. **Batches** each run into a single cursor-position + write operation
4. **Transmits** only the minimal necessary commands to the display

For example, if characters 5-10 changed on row 1:
- **Old approach**: 6 separate cursor+char commands (30 bytes)
- **New approach**: 1 cursor position + 6 characters (10 bytes)

This batching happens automatically—you only need to call `write_frame()` with the complete frame content.

## 3. Test with DisplaySimulator

Enable the simulator on a `DiffAnimator` instance to verify output without hardware:

```
animator = DiffAnimator(mock_display, enable_simulator=True)
custom_animation(animator)
sim = animator.get_simulator()
sim.assert_line_contains(1, "EXPECTED")

# DisplaySimulator uses 1-based indexing for all coordinates

```

The simulator tracks the display state and provides assertion helpers. For interactive debugging, instantiate `DiffAnimator` with `render_console=True` to display the simulator's contents in your terminal and observe each frame as it would appear on hardware.

`demo_animations.py` lets you choose any built-in animation by name. Animations loop indefinitely unless a `--duration` is provided. Frames are rendered in the console by default; pass `--no-render-console` to disable it. Use `--debug` for verbose logging.

## 4. Integrate into `ASCIIAnimations`

Add a wrapper method that forwards to your new function so demos can call it easily.

## 5. Document Behavior

Include relevant details about the animation's frame sequence and any special considerations.

## Animation Design Best Practices

### Optimizing for Performance

**Good patterns** (low bandwidth, smooth):
- Single bouncing character (2-4 chars/frame)
- Scrolling text with fixed elements (20-25 chars/frame)
- Pulsing center patterns (10-15 chars/frame)
- Sparse particle effects (<30% screen coverage)

**Challenging patterns** (high bandwidth):
- Random full-screen noise (30-40 chars/frame)
- Rapid cross-fades between full screens
- Multiple simultaneous fast-moving elements

### Frame Rate Guidelines

- **Sparse animations** (<10% changes): Target 10-15 FPS
- **Moderate animations** (10-30% changes): Target 6-8 FPS
- **Dense animations** (>30% changes): Target 4-5 FPS

The `DiffAnimator` will automatically handle the batching and transmission—these targets account for serial bandwidth limitations.

### Testing Your Animation

Run the comprehensive test suite to validate correctness:

```
python3 test_batched_diff.py

```

This runs 10 animation patterns (scrolling, bouncing, alternating, etc.) to ensure the batched diff implementation works correctly for various update patterns.

## Troubleshooting

### Animation is Stuttering or Lagging

**Cause**: Too many characters changing per frame for the target frame rate.

**Solution**:
- Reduce frame rate to match animation complexity
- Simplify animation to update fewer characters per frame
- Consider increasing baud rate to 19200 (2x faster, hardware permitting)

### Characters Appearing in Wrong Positions

**Cause**: String length mismatch (not padded to exactly 20 characters).

**Solution**: Always use `.ljust(20)` or `.center(20)` to ensure strings are exactly 20 characters.

```
line1 = my_text[:20].ljust(20)  # Truncate and pad

```

### Flickering Between Frames

**Cause**: If you see flickering, you may be using deprecated full-line write methods.

**Solution**: Always use `write_frame()`, never direct ESC Q A/B commands. The batched diff approach eliminates flicker by avoiding screen clears between frames.

---

Following this guide keeps new animations consistent with the optimized diff-based architecture and ensures they are testable and performant.
