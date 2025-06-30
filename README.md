# CD5220 VFD display controller library

Python library for controlling VFD (Vacuum Fluorescent Display) hardware which responds to the CD5220 command set.

**Disclaimer**: validated on a single display by a single developer, may be incomplete for your use case. Pull requests welcome.

The hardware tested only supports the 95 printable ASCII characters (codes 32-126). Extended characters are not guaranteed to render correctly.

## Overview

Controls 2×20 character VFD displays with features including:
- CD5220 command set support, RS232 serial connection (default 9600 baud, 8N1)
- Smart mode management with automatic transitions
- Continuous marquee scrolling (upper line only)
- Viewport overflow scrolling with a single window constraint
- Fast string writing modes
- Diff‑based ASCII animations via `DiffAnimator`
- Built-in simulator for hardware-free development
- Optional `DisplaySimulator` for animation testing (1-based coordinate API)
- In-terminal console rendering for debugging. Frames are shown only when text changes; non-visual commands log a note. Use `--console-verbose` to render unchanged frames.

## Installation

```bash
python -m venv venv
source ./venv/bin/activate  # activate this env in every new shell
pip install -r requirements.txt
```

Activate the virtual environment again whenever you open a new terminal:

```bash
source ./venv/bin/activate
```

## examples

```python
# display control
display.clear_display()
display.set_brightness(1-4)

# text writing  
display.write_positioned(text, col, row)
display.write_upper_line(text)
display.write_both_lines(upper, lower) 

# scrolling
display.scroll_marquee(text)
display.set_window(line, start_col, end_col)
display.enter_viewport_mode()
display.write_viewport(line, text, char_delay=None)
```

All coordinate parameters (columns and rows) are **1-based**. For example,
`display.set_cursor_position(1, 1)` moves the cursor to the upper-left corner.

### basic (simulator)
```python
from cd5220 import CD5220

display = CD5220()  # simulator only
display.write_both_lines("Hello", "World!")
```

### basic (hardware)
```python
from cd5220 import CD5220

with CD5220('/dev/ttyUSB0') as display:
    # fast string writing
    display.write_both_lines("Hello", "World!")

    # positioned text
    display.clear_display()
    display.write_positioned("CD5220 Demo", 1, 1)
```

### continuous scrolling
```python
with CD5220('/dev/ttyUSB0') as display:
    # auto-scrolling at ~1Hz
    display.scroll_marquee("This text scrolls continuously")
    time.sleep(10)
    display.clear_display()  # stop scrolling
```

### viewport 
```python
with CD5220('/dev/ttyUSB0') as display:
    # set up static text  
    display.write_positioned("ID: [", 1, 1)
    display.write_positioned("]", 16, 1)

    # set up constrained window (only one can be active)
    display.set_window(1, 5, 15)  # columns 5-15
    display.enter_viewport_mode()
    display.write_viewport(1, "VERY_LONG_IDENTIFIER_NAME")
    
    # fast writing (default)
    display.write_viewport(1, "VERY_LONG_IDENTIFIER_NAME")
    
    # character-by-character (≈ scrolling within viewport)
    display.write_viewport(1, "INCREMENTAL_TEXT", char_delay=0.2)
```

### POS display
```python
with CD5220('/dev/ttyUSB0') as display:
    display.write_both_lines("ITEM: COFFEE", "PRICE: $3.50")
    time.sleep(2)
    display.write_lower_line("PRICE: $2.99")  # quick update
```
### ASCII animations
```python
from animations import ASCIIAnimations

with CD5220('/dev/ttyUSB0') as display:
    # disable character delays but keep frame timing
    animations = ASCIIAnimations(
        display,
        sleep_fn=lambda _ : None,
        frame_sleep_fn=lambda _ : None,
    )
    animations.play_startup_sequence()
    # enable simulator for unit tests
    animations.enable_testing_mode()
    sim = animations.get_simulator()
    # animations update the display using minimal diffed writes
```

## Testing

Always activate the virtual environment before running any tests or demo
commands:

```bash
source ./venv/bin/activate
```

```bash
# run unit tests
python -m pytest tests/ -v

# hardware demo
python demo.py --port /dev/ttyUSB0 --demo all
python demo.py --port /dev/ttyUSB0 --demo scrolling --fast
python demo.py --port /dev/ttyUSB0 --demo ascii

python demo_animations.py --animation matrix --port /dev/ttyUSB0
python demo_animations.py --animation zen --port /dev/ttyUSB0 --debug --max_radius 8
python demo_animations.py --animation alert --port /dev/ttyUSB0 --message "HELLO"
# stars defaults: quantity 5, clustering 0.3, full_cycle 0.7, spawn_rate 1,
# wander 0.0
# quantity controls number of active stars (1-40)
# spawn_rate controls how quickly stars appear, spawning that many per frame
# clustering controls the likelihood of spawning adjacent stars
# wander controls how often stars relocate when a cycle completes
python demo_animations.py --animation stars --port /dev/ttyUSB0 \
    --quantity 20 --clustering 0.6 --full_cycle 0.8 \
    --spawn_rate 5

# simulator console output
python demo.py --console                # simulator only
python demo.py --port /dev/ttyUSB0 --console  # console + hardware
python demo.py --console --console-verbose    # console with non-visual frames
python demo.py --port /dev/ttyUSB0 --hardware-only  # hardware only
```

### Hardware Validation Tests

Run interactive validation to verify hardware output matches the built-in simulator. Spaces are shown using `\xb7` (middle dot) and marquee scrolling regions use `\u2190` (left arrow). Brightness level and cursor visibility are printed alongside the expected text so you can confirm non-textual settings. Whether the display is on or off is implied by whether any characters are shown. After each case the script asks whether the hardware matched and finally prints a formatted results table. Use `--case` to run a single validation by ID. Provide the serial port via the `VALIDATE_PORT` environment variable or as a command-line argument:

```bash
python validate_manual.py /dev/ttyUSB0
python validate_manual.py /dev/ttyUSB0 --case CURSOR
python validate_manual.py /dev/ttyUSB0 --case STATE
python validate_manual.py /dev/ttyUSB0 --console --console-verbose
```

## Developing Animations

Animations use the diff-based `DiffAnimator` API. See `README_ANIMATIONS.md` for a step-by-step guide on crafting frames and writing updates. The provided `DisplaySimulator` can be enabled on any animator instance for unit testing and visual verification. When debugging animations, enable `render_console=True` on a `DiffAnimator` or run `demo_animations.py` to watch a live simulation update in your terminal instead of verbose logging.

## Features Not Yet Implemented

These features are documented in the CD5220 manual but not implemented in this library:

- International character set selection (ESC f n)
- User-defined character download (ESC & s n m) 
- Font selection (ESC c n)
- EEPROM character storage (ESC s 1, ESC d 1)
- Peripheral device selection (ESC = n)

These may be added in future versions. Pull requests welcome.

## TODO

- Expand per-animation test coverage
- Continue improving analysis documentation
