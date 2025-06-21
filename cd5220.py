"""
CD5220 VFD Display Control Library with Smart Mode Management

The CD5220 operates in distinct documented modes:
- NORMAL: Full cursor control, brightness, positioning (default)
- STRING: Fast line writing via ESC Q A/B (incompatible with cursor commands)
- SCROLL: Continuous scrolling via ESC Q D/C (incompatible with cursor commands)

Smart mode management automatically handles transitions to maintain functionality
while preserving user content when possible.

Hardware Specifications:
- 2 rows × 20 columns VFD display
- Single unidirectional RS232 interface (9600 baud default)
- Scroll refresh rate: ~1Hz (hardware dependent)
- Mode settling time: ~200ms
"""

import serial
import time
import logging
from typing import Union, Optional, Dict, Any
from enum import Enum

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s [CD5220] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('CD5220')

class DisplayMode(Enum):
    """CD5220 operational modes as documented in manual."""
    NORMAL = "normal"          # Full cursor/ESC command support
    STRING = "string"          # ESC Q A/B mode - fast but limited to CLR/CAN
    SCROLL = "scroll"          # ESC Q D/C mode - continuous scrolling

class CD5220DisplayError(Exception):
    """Custom exception for CD5220 display errors."""
    pass

class CD5220:
    """
    CD5220 VFD Display Controller with Smart Mode Management
    
    OPERATIONAL MODES (as documented):
    
    1. NORMAL MODE (default):
       - Full cursor positioning and movement
       - Brightness control, display modes
       - Manual ASCII writing, all ESC commands
    
    2. STRING MODE:
       - Fast line writing with ESC Q A (upper) / ESC Q B (lower)
       - Automatic padding and formatting
       - ONLY CLR/CAN commands work in this mode
    
    3. SCROLL MODE:
       - Continuous scrolling with ESC Q D/C
       - Scrolls until new command received
       - ONLY CLR/CAN commands work in this mode
    
    SMART MODE MANAGEMENT:
    - Automatically clears display when needed for mode transitions
    - Only clears when transitioning FROM STRING/SCROLL to NORMAL-only commands
    - Preserves content when possible
    - Configurable behavior for advanced users
    
    HARDWARE TIMING CONSTANTS:
    - Scroll refresh rate: ~1Hz (display dependent)
    - Mode settling time: 200ms
    - Brightness change time: 300ms
    """
    
    DISPLAY_WIDTH = 20
    DISPLAY_HEIGHT = 2
    
    # Hardware timing constants
    SCROLL_REFRESH_RATE = 1.0  # Hz - hardware dependent
    MODE_SETTLING_TIME = 0.2   # seconds
    BRIGHTNESS_CHANGE_TIME = 0.3  # seconds
    
    # Core control commands
    CMD_CLEAR = b'\x0C'                    # Clear display (returns to normal mode)
    CMD_CANCEL = b'\x18'                   # Cancel current line (returns to normal mode)
    CMD_INITIALIZE = b'\x1B\x40'           # Initialize display
    
    # Normal mode commands
    CMD_OVERWRITE_MODE = b'\x1B\x11'       # Overwrite mode
    CMD_VERTICAL_SCROLL = b'\x1B\x12'      # Vertical scroll mode
    CMD_HORIZONTAL_SCROLL = b'\x1B\x13'    # Horizontal scroll mode
    CMD_CURSOR_ON = b'\x1B\x5F\x01'        # Cursor on
    CMD_CURSOR_OFF = b'\x1B\x5F\x00'       # Cursor off
    CMD_CURSOR_POSITION = b'\x1B\x6C'      # Set cursor position
    CMD_CURSOR_UP = b'\x1B\x5B\x41'        # Cursor up
    CMD_CURSOR_DOWN = b'\x1B\x5B\x42'      # Cursor down
    CMD_CURSOR_LEFT = b'\x1B\x5B\x44'      # Cursor left
    CMD_CURSOR_RIGHT = b'\x1B\x5B\x43'     # Cursor right
    CMD_CURSOR_HOME = b'\x1B\x5B\x48'      # Cursor home
    CMD_BRIGHTNESS = b'\x1B\x2A'           # Set brightness
    CMD_DISPLAY_ON = b'\x1B\x3D'           # Display on
    CMD_DISPLAY_OFF = b'\x1B\x3C'          # Display off
    
    # String mode commands (enter string mode)
    CMD_STRING_UPPER = b'\x1B\x51\x41'     # ESC Q A - Upper line string mode
    CMD_STRING_LOWER = b'\x1B\x51\x42'     # ESC Q B - Lower line string mode
    
    # Scroll mode commands (enter scroll mode)
    CMD_SCROLL_UPPER = b'\x1B\x51\x44'     # ESC Q D - Upper line scroll mode
    CMD_SCROLL_LOWER = b'\x1B\x51\x43'     # ESC Q C - Lower line scroll mode
    
    # Font and display control
    CMD_INTERNATIONAL_FONT = b'\x1B\x66'   # International font selection
    CMD_EXTENDED_FONT = b'\x1B\x63'        # Extended font selection

    def __init__(self, serial_port: Union[str, serial.Serial], 
                 baudrate: int = 9600, debug: bool = True,
                 auto_clear_mode_transitions: bool = True,
                 warn_on_mode_transitions: bool = True,
                 command_delay: float = 0.05,
                 bulk_delay_multiplier: float = 2.0):
        """
        Initialize CD5220 controller with smart mode management.
        
        Args:
            serial_port: Serial port device or existing Serial object
            baudrate: Communication baud rate (default 9600)
            debug: Enable debug logging
            auto_clear_mode_transitions: Automatically clear when transitioning from 
                                       STRING/SCROLL modes to NORMAL-only commands
            warn_on_mode_transitions: Log warnings when mode transitions occur
            command_delay: Default delay between commands (seconds)
            bulk_delay_multiplier: Multiplier for large payload delays
        """
        self.debug = debug
        self.auto_clear_mode_transitions = auto_clear_mode_transitions
        self.warn_on_mode_transitions = warn_on_mode_transitions
        self.default_delay = command_delay
        self.bulk_multiplier = bulk_delay_multiplier
        self._current_mode = DisplayMode.NORMAL
        
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
            
            # Initialize to normal mode
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
        """
        Send command with debug logging and adaptive timing control.
        
        Args:
            command: Command bytes to send
            delay: Override delay (uses adaptive delay if None)
            description: Description for logging
        """
        try:
            if delay is None:
                # Scale delay based on payload size for bulk operations
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

    def get_display_info(self) -> Dict[str, Any]:
        """Return current display state information for debugging."""
        return {
            'mode': self.current_mode.value,
            'auto_clear': self.auto_clear_mode_transitions,
            'warn_transitions': self.warn_on_mode_transitions,
            'default_delay': self.default_delay,
            'bulk_multiplier': self.bulk_multiplier
        }

    def _ensure_normal_mode(self, operation: str, force_clear: bool = False) -> bool:
        """
        Ensure display is in normal mode for operations that require it.
        
        Args:
            operation: Description of the operation requiring normal mode
            force_clear: Force clearing regardless of auto_clear setting
            
        Returns:
            bool: True if mode was changed, False if already in normal mode
        """
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

    # === MODE CONTROL ===
    
    def clear_display(self) -> None:
        """Clear display and return to normal mode."""
        self._send_command(self.CMD_CLEAR, 0.1, "Clear display")
        self._current_mode = DisplayMode.NORMAL

    def cancel_current_line(self) -> None:
        """
        Cancel current line and return to normal mode.
        
        Alternative to clear_display() that exits STRING/SCROLL modes
        without clearing the entire display content.
        """
        self._send_command(self.CMD_CANCEL, 0.1, "Cancel current line")
        self._current_mode = DisplayMode.NORMAL

    def initialize(self) -> None:
        """Initialize display and return to normal mode."""
        self._send_command(self.CMD_INITIALIZE, 0.2, "Initialize display")
        self._send_command(self.CMD_CLEAR, 0.1, "Clear after init")
        self._current_mode = DisplayMode.NORMAL

    def restore_defaults(self) -> None:
        """
        Restore factory defaults: brightness 4, overwrite mode, cursor off.
        
        This method ensures the display is in a predictable state for
        subsequent operations and is recommended between test sequences.
        """
        self.clear_display()
        self.set_brightness(4)
        self.set_overwrite_mode() 
        self.cursor_off()

    # === NORMAL MODE METHODS ===
    
    def set_overwrite_mode(self) -> None:
        """
        Set overwrite mode (normal mode only).
        
        In overwrite mode, new characters replace existing ones at cursor position.
        This is the default mode and recommended for most applications.
        """
        self._ensure_normal_mode("Overwrite mode")
        self._send_command(self.CMD_OVERWRITE_MODE, 0.1, "Set overwrite mode")

    def set_vertical_scroll_mode(self) -> None:
        """
        Set vertical scroll mode (normal mode only).
        
        **Note**: This mode is persistent until overwrite_mode is restored.
        In vertical scroll mode, line feeds cause the display to scroll vertically.
        """
        self._ensure_normal_mode("Vertical scroll mode")
        self._send_command(self.CMD_VERTICAL_SCROLL, 0.1, "Set vertical scroll mode")

    def set_horizontal_scroll_mode(self) -> None:
        """
        Set horizontal scroll mode (normal mode only).
        
        **Note**: This mode is persistent until overwrite_mode is restored.
        In horizontal scroll mode, characters beyond line width cause horizontal scrolling.
        """
        self._ensure_normal_mode("Horizontal scroll mode")
        self._send_command(self.CMD_HORIZONTAL_SCROLL, 0.1, "Set horizontal scroll mode")

    def set_brightness(self, level: int) -> None:
        """
        Set display brightness (normal mode only).
        
        Args:
            level: Brightness level 1-4 (1=dimmest, 4=brightest)
            
        Raises:
            CD5220DisplayError: If level is not in range 1-4
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
            
        Raises:
            CD5220DisplayError: If position is out of bounds
        """
        if row not in (1, 2):
            raise CD5220DisplayError("Row must be 1 or 2")
        if not 1 <= col <= self.DISPLAY_WIDTH:
            raise CD5220DisplayError(f"Column must be 1-{self.DISPLAY_WIDTH}")
        
        self._ensure_normal_mode("Cursor positioning")
        cmd = self.CMD_CURSOR_POSITION + bytes([col, row])
        self._send_command(cmd, 0.1, f"Set cursor: ({col},{row})")

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
        """
        Write text at current cursor position (normal mode only).
        
        Args:
            text: Text to write (raw ASCII)
        """
        self._ensure_normal_mode("Cursor writing")
        self._send_command(text.encode('ascii', 'ignore'), None, f"Write at cursor: '{text}'")

    def write_positioned(self, text: str, col: int, row: int) -> None:
        """
        Write text at specific position (normal mode only).
        
        Args:
            text: Text to write
            col: Column 1-20
            row: Row 1-2
        """
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
        
        This method puts the display in STRING mode, which provides fast,
        formatted line writing with automatic padding to 20 characters.
        
        **Hardware Constraint**: Once in STRING mode, only clear_display() 
        or cancel_current_line() will restore NORMAL mode functionality.
        
        Args:
            text: Text to display (truncated to 20 chars if longer)
            
        Example:
            >>> display.write_upper_line_string("SALES TOTAL")
            >>> display.current_mode
            <DisplayMode.STRING: 'string'>
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
        
        Fast, formatted line writing. Automatically pads to 20 characters.
        Puts display in string mode - only clear_display() or cancel_current_line() 
        will restore normal mode functionality.
        
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
        """
        Write to both lines using string mode.
        
        Args:
            upper: Upper line text
            lower: Lower line text
        """
        self.write_upper_line_string(upper)
        self.write_lower_line_string(lower)

    # === SCROLL MODE METHODS ===
    
    def scroll_upper_line(self, text: str, observe_duration: float = None) -> None:
        """
        Start continuous scrolling on upper line (ESC Q D).
        
        Text scrolls continuously until a new command is received.
        Puts display in scroll mode.
        
        Args:
            text: Text to scroll (can exceed 20 characters)
            observe_duration: Recommended viewing time (defaults to text length / refresh rate)
        """
        cmd = self.CMD_SCROLL_UPPER + text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, None, f"Scroll upper: '{text}'")
        self._current_mode = DisplayMode.SCROLL
        
        if observe_duration is None:
            # Calculate minimum observation time for text visibility
            observe_duration = max(8.0, len(text) / self.SCROLL_REFRESH_RATE * 0.5)
        
        logger.info(f"Scrolling for {observe_duration:.1f}s at ~{self.SCROLL_REFRESH_RATE}Hz")

    def scroll_lower_line(self, text: str, observe_duration: float = None) -> None:
        """
        Start continuous scrolling on lower line (ESC Q C).
        
        Text scrolls continuously until a new command is received.
        Puts display in scroll mode.
        
        Args:
            text: Text to scroll (can exceed 20 characters)
            observe_duration: Recommended viewing time (defaults to text length / refresh rate)
        """
        cmd = self.CMD_SCROLL_LOWER + text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, None, f"Scroll lower: '{text}'")
        self._current_mode = DisplayMode.SCROLL
        
        if observe_duration is None:
            # Calculate minimum observation time for text visibility
            observe_duration = max(8.0, len(text) / self.SCROLL_REFRESH_RATE * 0.5)
        
        logger.info(f"Scrolling for {observe_duration:.1f}s at ~{self.SCROLL_REFRESH_RATE}Hz")

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
        """
        Display a message with automatic line wrapping.
        
        Args:
            message: Message to display
            duration: Display duration in seconds
            mode: "string" (fast) or "normal" (with cursor support)
        """
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
