# CD5220 VFD display controller library

Python library for controlling VFD (Vacuum Fluorescent Display) hardware which responds to the CD5220 command set.

**Disclaimer**: validated on a single display by a single developer, may be incomplete for your use case. Pull requests welcome.

## Overview

Controls 2×20 character VFD displays with features including:
- Smart mode management with automatic transitions
- Continuous marquee scrolling (upper line only)
- Viewport overflow scrolling with window constraints  
- Fast string writing modes
- CD5220 command set support, RS232 serial connection (default 9600 baud, 8N1)

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
display.write_upper_line_string(text)
display.write_both_lines_string(upper, lower) 

# scrolling
display.scroll_marquee(text)
display.set_window(line, start_col, end_col)
display.enter_viewport_mode()
display.write_viewport(line, text)
```

### basic
```python
from cd5220 import CD5220

with CD5220('/dev/ttyUSB0') as display:
    # fast string writing
    display.write_both_lines_string("Hello", "World!")
    
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

### viewport scrolling
```python
with CD5220('/dev/ttyUSB0') as display:
    # set up constrained window
    display.write_positioned("ID: [", 1, 1)
    display.write_positioned("]", 16, 1)
    
    display.set_window(1, 5, 15)  # columns 5-15
    display.enter_viewport_mode()
    display.write_viewport(1, "VERY_LONG_IDENTIFIER_NAME")
```

### POS display
```python
with CD5220('/dev/ttyUSB0') as display:
    display.write_both_lines_string("ITEM: COFFEE", "PRICE: $3.50")
    time.sleep(2)
    display.write_lower_line_string("PRICE: $2.99")  # quick update
```
