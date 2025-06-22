# CD5220 VFD display controller library

Python library for controlling VFD (Vacuum Fluorescent Display) hardware which responds to the CD5220 command set.

**Disclaimer**: validated on a single display by a single developer, may be incomplete for your use case. Pull requests welcome.

## Overview

Controls 2×20 character VFD displays with features including:
- CD5220 command set support, RS232 serial connection (default 9600 baud, 8N1)
- Smart mode management with automatic transitions
- Continuous marquee scrolling (upper line only)
- Viewport overflow scrolling with a single window constraint
- Fast string writing modes
- Diff‑based ASCII animations via `DiffAnimator`
- Optional `DisplaySimulator` for animation testing
- In-terminal console rendering of animations for visual debugging

## Installation

```bash
python -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
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

### basic
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
from cd5220 import CD5220ASCIIAnimations

with CD5220('/dev/ttyUSB0') as display:
    # disable character delays but keep frame timing
    animations = CD5220ASCIIAnimations(
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

```bash
# run unit tests
python -m pytest tests/ -v

# hardware demo
python demo.py --port /dev/ttyUSB0 --demo all
python demo.py --port /dev/ttyUSB0 --demo scrolling --fast
python demo.py --port /dev/ttyUSB0 --demo ascii
python demo_animations.py --port /dev/ttyUSB0
python demo_animations.py --port /dev/ttyUSB0 --debug
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
