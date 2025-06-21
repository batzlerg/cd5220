"""
CD5220 VFD Display Control Library

Python interface for CD5220 VFD displays with smart mode management.
Supports string mode, continuous scrolling, and window-constrained viewport operations.
"""

import serial
import time
import logging
from typing import Union, Optional, Dict, Any, Tuple
from enum import Enum

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s [CD5220] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('CD5220')

class DisplayMode(Enum):
    """CD5220 operational modes."""
    NORMAL = "normal"
    STRING = "string"
    SCROLL = "scroll"
    VIEWPORT = "viewport"

class CD5220DisplayError(Exception):
    """Custom exception for CD5220 display errors."""
    pass

class CD5220:
    """
    CD5220 VFD Display Controller with Smart Mode Management
    
    Key Features:
    - Smart mode transitions with configurable auto-clear behavior
    - String mode for fast line writing (ESC Q A/B)
    - Continuous marquee scrolling (ESC Q D, upper line only)
    - Window-constrained viewport mode (ESC W + ESC DC3)
    - Hardware-aware timing and error handling
    
    Basic Usage:
        with CD5220('/dev/ttyUSB0') as display:
            display.write_both_lines_string("Hello", "World")
            display.scroll_marquee("Scrolling text...")
    
    Mode Management:
    - NORMAL: Full cursor/ESC command support (default)
    - STRING: Fast line writing, limited to CLR/CAN commands
    - SCROLL: Continuous scrolling, limited to CLR/CAN commands  
    - VIEWPORT: Window-constrained display, limited to CLR/CAN commands
    """
    
    DISPLAY_WIDTH = 20
    DISPLAY_HEIGHT = 2
    
    # Hardware timing constants
    SCROLL_REFRESH_RATE = 1.0  # Hz
    MODE_SETTLING_TIME = 0.2   # seconds
    BRIGHTNESS_CHANGE_TIME = 0.3  # seconds
    
    # Core control commands
    CMD_CLEAR = b'\x0C'
    CMD_CANCEL = b'\x18'
    CMD_INITIALIZE = b'\x1B\x40'
    
    # Normal mode commands
    CMD_OVERWRITE_MODE = b'\x1B\x11'
    CMD_VERTICAL_SCROLL = b'\x1B\x12'
    CMD_HORIZONTAL_SCROLL = b'\x1B\x13'
    CMD_CURSOR_ON = b'\x1B\x5F\x01'
    CMD_CURSOR_OFF = b'\x1B\x5F\x00'
    CMD_CURSOR_POSITION = b'\x1B\x6C'
    CMD_CURSOR_UP = b'\x1B\x5B\x41'
    CMD_CURSOR_DOWN = b'\x1B\x5B\x42'
    CMD_CURSOR_LEFT = b'\x1B\x5B\x44'
    CMD_CURSOR_RIGHT = b'\x1B\x5B\x43'
    CMD_CURSOR_HOME = b'\x1B\x5B\x48'
    CMD_BRIGHTNESS = b'\x1B\x2A'
    CMD_DISPLAY_ON = b'\x1B\x3D'
    CMD_DISPLAY_OFF = b'\x1B\x3C'
    
    # String mode commands
    CMD_STRING_UPPER = b'\x1B\x51\x41'
    CMD_STRING_LOWER = b'\x1B\x51\x42'
    
    # Scroll mode commands
    CMD_SCROLL_MARQUEE = b'\x1B\x51\x44'
    
    # Window management commands
    CMD_WINDOW_SET = b'\x1B\x57'
    
    # Font and display control
    CMD_INTERNATIONAL_FONT = b'\x1B\x66'
    CMD_EXTENDED_FONT = b'\x1B\x63'

    def __init__(self, serial_port: Union[str, serial.Serial], 
                 baudrate: int = 9600, debug: bool = True,
                 auto_clear_mode_transitions: bool = True,
                 warn_on_mode_transitions: bool = True,
                 command_delay: float = 0.05,
                 bulk_delay_multiplier: float = 2.0):
        """
        Initialize CD5220 controller.
        
        Args:
            serial_port: Serial port device or existing Serial object
            baudrate: Communication baud rate (default 9600)
            debug: Enable debug logging
            auto_clear_mode_transitions: Auto-clear when mode conflicts occur
            warn_on_mode_transitions: Log warnings for mode transitions
            command_delay: Base delay between commands (seconds)
            bulk_delay_multiplier: Multiplier for large payload delays
        """
        self.debug = debug
        self.auto_clear_mode_transitions = auto_clear_mode_transitions
        self.warn_on_mode_transitions = warn_on_mode_transitions
        self.default_delay = command_delay
        self.bulk_multiplier = bulk_delay_multiplier
        self._current_mode = DisplayMode.NORMAL
        self._active_windows = {}
        
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Initializing CD5220 controller")
        
        try:
            if isinstance(serial_port, str):
                logger.debug(f"Opening serial port: {serial_port} at {baudrate} baud")
                self.ser = serial.Serial(
                    port=serial_port,
                    baudrate=baudrate,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=1,
                    write_timeout=1
                )
            else:
                logger.debug("Using existing serial connection")
                self.ser = serial_port
            
            time.sleep(0.1)
            self._send_command(self.CMD_INITIALIZE, 0.2, "Initialize display")
            self.restore_defaults()
            
        except (serial.SerialException, serial.SerialTimeoutException) as e:
            logger.error(f"Serial connection failed: {e}")
            raise CD5220DisplayError(f"Serial connection failed: {e}")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise CD5220DisplayError(f"Initialization failed: {e}")

    def _send_command(self, command: bytes, delay: float = None, description: str = "Command") -> None:
        """Send command with debug logging and adaptive timing."""
        try:
            if delay is None:
                delay = self.default_delay * (1 + len(command) / 20 * self.bulk_multiplier)
            
            hex_str = ' '.join(f'{byte:02X}' for byte in command)
            logger.debug(f"Sending: {description} | Bytes: {hex_str} | Delay: {delay:.3f}s")
            
            self.ser.write(command)
            self.ser.flush()
            time.sleep(delay)
        except (serial.SerialException, serial.SerialTimeoutException) as e:
            logger.error(f"Command failed: {e}")
            raise CD5220DisplayError(f"Command failed: {e}")

    @property
    def current_mode(self) -> DisplayMode:
        """Get current display mode."""
        return self._current_mode

    @property
    def active_windows(self) -> Dict[int, Tuple[int, int]]:
        """Get currently active window configurations."""
        return self._active_windows.copy()

    def get_display_info(self) -> Dict[str, Any]:
        """Return current display state information."""
        return {
            'mode': self.current_mode.value,
            'auto_clear': self.auto_clear_mode_transitions,
            'warn_transitions': self.warn_on_mode_transitions,
            'default_delay': self.default_delay,
            'bulk_multiplier': self.bulk_multiplier,
            'active_windows': self.active_windows
        }

    def _ensure_normal_mode(self, operation: str, force_clear: bool = False) -> bool:
        """Ensure display is in normal mode for operations that require it."""
        if self._current_mode == DisplayMode.NORMAL:
            return False
        
        if self.auto_clear_mode_transitions or force_clear:
            if self.warn_on_mode_transitions:
                logger.warning(f"{operation} requires normal mode. Auto-clearing from {self._current_mode.value} mode.")
            self.clear_display()
            return True
        else:
            if self.warn_on_mode_transitions:
                logger.error(f"{operation} requires normal mode. Currently in {self._current_mode.value} mode. "
                           f"Use clear_display() first or enable auto_clear_mode_transitions.")
            raise CD5220DisplayError(f"{operation} requires normal mode. Use clear_display() first.")

    def _send_cursor_position_raw(self, col: int, row: int) -> None:
        """Send cursor position command without mode checking."""
        cmd = self.CMD_CURSOR_POSITION + bytes([col, row])
        self._send_command(cmd, 0.1, f"Raw cursor: ({col},{row})")

    def _write_text_raw(self, text: str) -> None:
        """Send text without mode checking."""
        self._send_command(text.encode('ascii', 'ignore'), None, f"Raw write: '{text}'")

    # === MODE CONTROL ===
    
    def clear_display(self) -> None:
        """Clear display and return to normal mode."""
        self._send_command(self.CMD_CLEAR, 0.1, "Clear display")
        self._current_mode = DisplayMode.NORMAL
        self._active_windows = {}

    def cancel_current_line(self) -> None:
        """Cancel current line and return to normal mode."""
        self._send_command(self.CMD_CANCEL, 0.1, "Cancel current line")
        self._current_mode = DisplayMode.NORMAL

    def initialize(self) -> None:
        """Initialize display and return to normal mode."""
        self._send_command(self.CMD_INITIALIZE, 0.2, "Initialize display")
        self._send_command(self.CMD_CLEAR, 0.1, "Clear after init")
        self._current_mode = DisplayMode.NORMAL
        self._active_windows = {}

    def restore_defaults(self) -> None:
        """Restore factory defaults: brightness 4, overwrite mode, cursor off."""
        self.clear_display()
        self.set_brightness(4)
        self.set_overwrite_mode() 
        self.cursor_off()

    # === NORMAL MODE METHODS ===
    
    def set_overwrite_mode(self) -> None:
        """Set overwrite mode (normal mode only)."""
        self._ensure_normal_mode("Overwrite mode")
        self._send_command(self.CMD_OVERWRITE_MODE, 0.1, "Set overwrite mode")

    def set_vertical_scroll_mode(self) -> None:
        """Set vertical scroll mode (normal mode only)."""
        self._ensure_normal_mode("Vertical scroll mode")
        self._send_command(self.CMD_VERTICAL_SCROLL, 0.1, "Set vertical scroll mode")

    def set_horizontal_scroll_mode(self) -> None:
        """Set horizontal scroll mode (normal mode only)."""
        self._ensure_normal_mode("Horizontal scroll mode")
        self._send_command(self.CMD_HORIZONTAL_SCROLL, 0.1, "Set horizontal scroll mode")

    def set_brightness(self, level: int) -> None:
        """
        Set display brightness (normal mode only).
        
        Args:
            level: Brightness level 1-4 (1=dimmest, 4=brightest)
        """
        if not 1 <= level <= 4:
            raise CD5220DisplayError(f"Invalid brightness level: {level} (must be 1-4)")
        
        self._ensure_normal_mode("Brightness control")
        cmd = self.CMD_BRIGHTNESS + bytes([level])
        self._send_command(cmd, self.BRIGHTNESS_CHANGE_TIME, f"Set brightness: {level}")

    def cursor_on(self) -> None:
        """Enable cursor (normal mode only)."""
        self._ensure_normal_mode("Cursor control")
        self._send_command(self.CMD_CURSOR_ON, 0.1, "Cursor on")

    def cursor_off(self) -> None:
        """Disable cursor (normal mode only)."""
        self._ensure_normal_mode("Cursor control")
        self._send_command(self.CMD_CURSOR_OFF, 0.1, "Cursor off")

    def set_cursor_position(self, col: int, row: int) -> None:
        """
        Set cursor position (normal mode only).
        
        Args:
            col: Column 1-20
            row: Row 1-2
        """
        if row not in (1, 2):
            raise CD5220DisplayError("Row must be 1 or 2")
        if not 1 <= col <= self.DISPLAY_WIDTH:
            raise CD5220DisplayError(f"Column must be 1-{self.DISPLAY_WIDTH}")
        
        self._ensure_normal_mode("Cursor positioning")
        self._send_cursor_position_raw(col, row)

    def cursor_move_up(self) -> None:
        """Move cursor up (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_UP, 0.1, "Cursor up")

    def cursor_move_down(self) -> None:
        """Move cursor down (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_DOWN, 0.1, "Cursor down")

    def cursor_move_left(self) -> None:
        """Move cursor left (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_LEFT, 0.1, "Cursor left")

    def cursor_move_right(self) -> None:
        """Move cursor right (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_RIGHT, 0.1, "Cursor right")

    def cursor_home(self) -> None:
        """Move cursor to home position (1,1) (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_HOME, 0.1, "Cursor home")

    def write_at_cursor(self, text: str) -> None:
        """Write text at current cursor position (normal mode only)."""
        self._ensure_normal_mode("Cursor writing")
        self._write_text_raw(text)

    def write_positioned(self, text: str, col: int, row: int) -> None:
        """Write text at specific position (normal mode only)."""
        self.set_cursor_position(col, row)
        self.write_at_cursor(text)

    def display_on(self) -> None:
        """Turn display on (normal mode only)."""
        self._ensure_normal_mode("Display control")
        self._send_command(self.CMD_DISPLAY_ON, 0.1, "Display on")

    def display_off(self) -> None:
        """Turn display off (normal mode only)."""
        self._ensure_normal_mode("Display control")
        self._send_command(self.CMD_DISPLAY_OFF, 0.1, "Display off")

    # === STRING MODE METHODS ===
    
    def write_upper_line_string(self, text: str) -> None:
        """
        Write to upper line using fast string mode (ESC Q A).
        
        Enters STRING mode - only clear_display() or cancel_current_line() 
        will restore NORMAL mode functionality.
        
        Args:
            text: Text to display (truncated to 20 chars if longer)
        """
        if len(text) > self.DISPLAY_WIDTH:
            text = text[:self.DISPLAY_WIDTH]
        padded_text = text.ljust(self.DISPLAY_WIDTH)
        cmd = self.CMD_STRING_UPPER + padded_text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, None, f"String upper: '{text}'")
        self._current_mode = DisplayMode.STRING

    def write_lower_line_string(self, text: str) -> None:
        """
        Write to lower line using fast string mode (ESC Q B).
        
        Args:
            text: Text to display (truncated to 20 chars if longer)
        """
        if len(text) > self.DISPLAY_WIDTH:
            text = text[:self.DISPLAY_WIDTH]
        padded_text = text.ljust(self.DISPLAY_WIDTH)
        cmd = self.CMD_STRING_LOWER + padded_text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, None, f"String lower: '{text}'")
        self._current_mode = DisplayMode.STRING

    def write_both_lines_string(self, upper: str, lower: str) -> None:
        """Write to both lines using string mode."""
        self.write_upper_line_string(upper)
        self.write_lower_line_string(lower)

    # === CONTINUOUS SCROLLING METHODS ===
    
    def scroll_marquee(self, text: str, observe_duration: float = None) -> None:
        """
        Start continuous marquee scrolling on upper line (ESC Q D).
        
        Hardware limitation: Upper line only.
        
        Args:
            text: Text to scroll
            observe_duration: Recommended viewing time
        """
        cmd = self.CMD_SCROLL_MARQUEE + text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, None, f"Scroll marquee: '{text}'")
        self._current_mode = DisplayMode.SCROLL
        
        if observe_duration is None:
            observe_duration = max(8.0, len(text) / self.SCROLL_REFRESH_RATE * 0.5)
        
        logger.info(f"Marquee scrolling for {observe_duration:.1f}s at ~{self.SCROLL_REFRESH_RATE}Hz")

    # === WINDOW MANAGEMENT METHODS ===
    
    def set_window(self, line: int, start_col: int, end_col: int) -> None:
        """
        Set window range for viewport mode (normal mode only).
        
        Uses consistent 1-based indexing. Window boundaries match writing positions.

        Args:
            line: Line number (1 or 2)
            start_col: Starting column (1-20) - writing begins here
            end_col: Ending column (start_col to 20) - writing ends here
        """
        if line not in (1, 2):
            raise CD5220DisplayError("Line must be 1 or 2")
        if not 1 <= start_col <= end_col <= self.DISPLAY_WIDTH:
            raise CD5220DisplayError(f"Invalid window range: start={start_col}, end={end_col}")
        
        self._ensure_normal_mode("Window management")
        
        # Convert from 1-based API coordinates to 0-based hardware coordinates
        hw_start_col = start_col - 1
        hw_end_col = end_col - 1

        cmd = self.CMD_WINDOW_SET + bytes([1, hw_start_col, hw_end_col, line])
        self._send_command(cmd, 0.1, f"Set window: line {line}, cols {start_col}-{end_col}")
        self._active_windows[line] = (start_col, end_col)  # Store API coordinates for consistency


    def clear_window(self, line: int) -> None:
        """Clear window range for specified line (normal mode only)."""
        if line not in (1, 2):
            raise CD5220DisplayError("Line must be 1 or 2")
        
        self._ensure_normal_mode("Window management")
        
        cmd = self.CMD_WINDOW_SET + bytes([0, 0, 0, line])
        self._send_command(cmd, 0.1, f"Clear window: line {line}")
        
        if line in self._active_windows:
            del self._active_windows[line]

    def clear_all_windows(self) -> None:
        """Clear all window ranges (normal mode only)."""
        self._ensure_normal_mode("Window management")
        
        for line in [1, 2]:
            if line in self._active_windows:
                self.clear_window(line)

    def enter_viewport_mode(self) -> None:
        """
        Enter viewport mode for window-constrained display.
        
        Requires windows to be set first using set_window().
        """
        if not self._active_windows:
            raise CD5220DisplayError("No windows configured. Use set_window() first.")
        
        self._ensure_normal_mode("Viewport mode entry")
        self.set_horizontal_scroll_mode()
        self._current_mode = DisplayMode.VIEWPORT
        
        logger.info(f"Entered viewport mode with windows: {self._active_windows}")

    def write_viewport(self, line: int, text: str, char_delay: float = None) -> None:
        """
        Write text to viewport window with optional smooth character building.
        
        Args:
            line: Line number (1 or 2)
            text: Text to write
            char_delay: If None, writes all text at once (fast).
                       If specified, writes character-by-character with delay (smooth building effect).
        """
        if self._current_mode != DisplayMode.VIEWPORT:
            raise CD5220DisplayError("Must be in viewport mode. Use enter_viewport_mode() first.")
        
        if line not in self._active_windows:
            raise CD5220DisplayError(f"No window configured for line {line}")
        
        start_col, end_col = self._active_windows[line]
        
        if char_delay is None:
            # Fast mode: write entire text at once (original behavior)
            self._send_cursor_position_raw(start_col, line)
            self._write_text_raw(text)
            logger.debug(f"Viewport write: line {line}, window {start_col}-{end_col}, text: '{text}'")
        else:
            # Smooth mode: character-by-character building with hardware cursor management
            self._send_cursor_position_raw(start_col, line)
            logger.debug(f"Viewport incremental write: line {line}, window {start_col}-{end_col}, text: '{text}'")

            for char in text:
                self._write_text_raw(char)
                time.sleep(char_delay)

    # === FONT CONTROL ===
    
    def set_international_font(self, font_id: int) -> None:
        """Set international font (normal mode only)."""
        self._ensure_normal_mode("Font selection")
        cmd = self.CMD_INTERNATIONAL_FONT + bytes([font_id])
        self._send_command(cmd, 0.1, f"Set international font: {font_id}")

    def set_extended_font(self, font_id: int) -> None:
        """Set extended font (normal mode only)."""
        self._ensure_normal_mode("Font selection")
        cmd = self.CMD_EXTENDED_FONT + bytes([font_id])
        self._send_command(cmd, 0.1, f"Set extended font: {font_id}")

    # === CONVENIENCE METHODS ===
    
    def display_message(self, message: str, duration: float = 2.0, mode: str = "string") -> None:
        """Display a message with automatic line wrapping."""
        lines = [message[i:i+self.DISPLAY_WIDTH] for i in range(0, len(message), self.DISPLAY_WIDTH)]
        
        if mode == "string":
            if len(lines) >= 1:
                self.write_upper_line_string(lines[0])
            if len(lines) >= 2:
                self.write_lower_line_string(lines[1])
        else:  # normal mode
            self.clear_display()
            if len(lines) >= 1:
                self.write_positioned(lines[0], 1, 1)
            if len(lines) >= 2:
                self.write_positioned(lines[1], 1, 2)
        
        time.sleep(duration)

    # === LEGACY COMPATIBILITY METHODS ===
    
    def write_upper_line(self, text: str) -> None:
        """Legacy method: Write to upper line using string mode."""
        self.write_upper_line_string(text)

    def write_lower_line(self, text: str) -> None:
        """Legacy method: Write to lower line using string mode."""
        self.write_lower_line_string(text)

    def write_both_lines(self, upper: str, lower: str) -> None:
        """Legacy method: Write to both lines using string mode."""
        self.write_both_lines_string(upper, lower)

    def scroll_upper_line(self, text: str, observe_duration: float = None) -> None:
        """Legacy method: Use scroll_marquee() instead."""
        logger.warning("scroll_upper_line() is deprecated. Use scroll_marquee() instead.")
        self.scroll_marquee(text, observe_duration)

    def close(self) -> None:
        """Close serial connection."""
        if hasattr(self, 'ser') and self.ser.is_open:
            try:
                logger.debug("Closing serial connection")
                self.ser.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
