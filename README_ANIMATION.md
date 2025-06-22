# Animation Development Guide

This document outlines the recommended process for creating new ASCII animations for the CD5220 display library. Animations rely on the `DiffAnimator` class which updates the hardware using minimal diffed writes and can be paired with `DisplaySimulator` for testing.

## 1. Plan the Animation

- Sketch the static portions of both display lines (20 characters each).
- Decide which characters will change each frame.
- Determine the desired frame rate and total duration.

## 2. Write the Animation Function

```python
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

`write_frame()` replaces the entire buffer each frame. Only changed characters are sent to the display.

## 3. Test with DisplaySimulator

Enable the simulator on a `DiffAnimator` instance to verify output without hardware:

```python
animator = DiffAnimator(mock_display, enable_simulator=True)
custom_animation(animator)
sim = animator.get_simulator()
sim.assert_line_contains(0, "EXPECTED")
```

The simulator tracks the display state and provides assertion helpers. For interactive debugging, instantiate ``DiffAnimator`` with ``render_console=True`` to display the simulator's contents in your terminal and observe each frame as it would appear on hardware. 

``demo_animations.py`` implements this by default with ``--render-console`` to see all built-in animations directly in your terminal. To make the frame output cleaner, it does not output debug logs by default - use ``--debug`` to include verbose logging alongside the frame output.

## 4. Integrate into `CD5220ASCIIAnimations`

Add a wrapper method that forwards to your new function so demos can call it easily.

## 5. Document Behavior

Include relevant details about the animation's frame sequence and any special considerations.

Following this guide keeps new animations consistent with the diff-based architecture and ensures they are testable.
