"""
CD5220 VFD Display Control Library (Complete)

Implements all documented CD5220 commands with comprehensive debug logging.
"""

import serial
import time
import logging
from typing import Union, Optional

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s [CD5220] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('CD5220')

class CD5220DisplayError(Exception):
    """Custom exception for CD5220 display errors."""
    pass

class CD5220:
    """Complete CD5220 controller with all documented features and debug logging."""
    
    DISPLAY_WIDTH = 20
    DISPLAY_HEIGHT = 2
    
    # Command constants (from documentation)
    CMD_CLEAR = b'\x0C'                    # Clear display
    CMD_CLEAR_LINE = b'\x18'               # Clear current line
    CMD_INITIALIZE = b'\x1B\x40'           # Initialize display
    CMD_OVERWRITE_MODE = b'\x1B\x11'       # Overwrite mode
    CMD_VERTICAL_SCROLL = b'\x1B\x12'      # Vertical scroll mode
    CMD_HORIZONTAL_SCROLL = b'\x1B\x13'    # Horizontal scroll mode
    CMD_UPPER_LINE = b'\x1B\x51\x41'       # ESC Q A - Upper line write
    CMD_LOWER_LINE = b'\x1B\x51\x42'       # ESC Q B - Lower line write
    CMD_UPPER_SCROLL = b'\x1B\x51\x44'     # ESC Q D - Upper line scroll
    CMD_LOWER_SCROLL = b'\x1B\x51\x43'     # ESC Q C - Lower line scroll
    CMD_CURSOR_ON = b'\x1B\x5F\x01'        # ESC _ 1 - Cursor on
    CMD_CURSOR_OFF = b'\x1B\x5F\x00'       # ESC _ 0 - Cursor off
    CMD_CURSOR_POSITION = b'\x1B\x6C'      # ESC l x y - Set cursor position
    CMD_CURSOR_UP = b'\x1B\x5B\x41'        # ESC [ A - Cursor up
    CMD_CURSOR_DOWN = b'\x1B\x5B\x42'      # ESC [ B - Cursor down
    CMD_CURSOR_LEFT = b'\x1B\x5B\x44'      # ESC [ D - Cursor left
    CMD_CURSOR_RIGHT = b'\x1B\x5B\x43'     # ESC [ C - Cursor right
    CMD_CURSOR_HOME = b'\x1B\x5B\x48'      # ESC [ H - Cursor home
    CMD_BRIGHTNESS = b'\x1B\x2A'           # ESC * n - Set brightness
    CMD_DISPLAY_ON = b'\x1B\x3D'           # Display on
    CMD_DISPLAY_OFF = b'\x1B\x3C'          # Display off
    CMD_INTERNATIONAL_FONT = b'\x1B\x66'   # ESC f n - Set international font
    CMD_EXTENDED_FONT = b'\x1B\x63'        # ESC c n - Set extended font

    def __init__(self, serial_port: Union[str, serial.Serial], 
                 baudrate: int = 9600, debug: bool = True):
        self.debug = debug
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
            
            # Initialize display
            time.sleep(0.1)
            self._send_command(self.CMD_INITIALIZE, 0.2, "Initialize display")
            self._send_command(self.CMD_CLEAR, 0.1, "Clear display")
            self._send_command(self.CMD_CURSOR_OFF, 0.1, "Cursor off")
            self._send_command(self.CMD_OVERWRITE_MODE, 0.1, "Set overwrite mode")
            
        except serial.SerialException as e:
            logger.error(f"Serial connection failed: {e}")
            raise CD5220DisplayError(f"Serial connection failed: {e}")

    def _send_command(self, command: bytes, delay: float = 0.05, description: str = "Command") -> None:
        """Send command with debug logging and timing control."""
        try:
            hex_str = ' '.join(f'{byte:02X}' for byte in command)
            logger.debug(f"Sending: {description} | Bytes: {hex_str}")
            
            self.ser.write(command)
            self.ser.flush()
            time.sleep(delay)
        except (serial.SerialException, serial.SerialTimeoutException) as e:
            logger.error(f"Command failed: {e}")
            raise CD5220DisplayError(f"Command failed: {e}")

    # Display Control Methods
    def clear_display(self) -> None:
        self._send_command(self.CMD_CLEAR, 0.1, "Clear display")

    def clear_current_line(self) -> None:
        self._send_command(self.CMD_CLEAR_LINE, 0.1, "Clear current line")

    def initialize(self) -> None:
        self._send_command(self.CMD_INITIALIZE, 0.2, "Initialize display")
        self._send_command(self.CMD_CLEAR, 0.1, "Clear after init")

    # Text Output Methods
    def write_upper_line(self, text: str) -> None:
        if len(text) > self.DISPLAY_WIDTH:
            text = text[:self.DISPLAY_WIDTH]
        padded_text = text.ljust(self.DISPLAY_WIDTH)
        cmd = self.CMD_UPPER_LINE + padded_text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, 0.1, f"Write upper: '{text}'")

    def write_lower_line(self, text: str) -> None:
        if len(text) > self.DISPLAY_WIDTH:
            text = text[:self.DISPLAY_WIDTH]
        padded_text = text.ljust(self.DISPLAY_WIDTH)
        cmd = self.CMD_LOWER_LINE + padded_text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, 0.1, f"Write lower: '{text}'")

    def write_both_lines(self, upper: str, lower: str) -> None:
        self.write_upper_line(upper)
        self.write_lower_line(lower)

    # Scrolling Methods
    def scroll_upper_line(self, text: str) -> None:
        cmd = self.CMD_UPPER_SCROLL + text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, 0.1, f"Scroll upper: '{text}'")

    def scroll_lower_line(self, text: str) -> None:
        cmd = self.CMD_LOWER_SCROLL + text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, 0.1, f"Scroll lower: '{text}'")

    # Cursor Control Methods
    def cursor_on(self) -> None:
        self._send_command(self.CMD_CURSOR_ON, 0.1, "Cursor on")

    def cursor_off(self) -> None:
        self._send_command(self.CMD_CURSOR_OFF, 0.1, "Cursor off")

    def set_cursor_position(self, col: int, row: int) -> None:
        if row not in (1, 2):
            raise CD5220DisplayError("Row must be 1 or 2")
        if not 1 <= col <= self.DISPLAY_WIDTH:
            raise CD5220DisplayError(f"Column must be 1-{self.DISPLAY_WIDTH}")
        
        cmd = self.CMD_CURSOR_POSITION + bytes([col, row])
        self._send_command(cmd, 0.1, f"Set cursor: ({col},{row})")

    def cursor_move_up(self) -> None:
        self._send_command(self.CMD_CURSOR_UP, 0.1, "Cursor up")

    def cursor_move_down(self) -> None:
        self._send_command(self.CMD_CURSOR_DOWN, 0.1, "Cursor down")

    def cursor_move_left(self) -> None:
        self._send_command(self.CMD_CURSOR_LEFT, 0.1, "Cursor left")

    def cursor_move_right(self) -> None:
        self._send_command(self.CMD_CURSOR_RIGHT, 0.1, "Cursor right")

    def cursor_home(self) -> None:
        self._send_command(self.CMD_CURSOR_HOME, 0.1, "Cursor home")

    # Brightness Control
    def set_brightness(self, level: int) -> None:
        if not 1 <= level <= 4:
            error_msg = f"Invalid brightness level: {level} (must be 1-4)"
            logger.error(error_msg)
            raise CD5220DisplayError(error_msg)
        
        cmd = self.CMD_BRIGHTNESS + bytes([level])
        self._send_command(cmd, 0.2, f"Set brightness: {level}")

    # Display Mode Methods
    def set_overwrite_mode(self) -> None:
        self._send_command(self.CMD_OVERWRITE_MODE, 0.1, "Set overwrite mode")

    def set_vertical_scroll_mode(self) -> None:
        self._send_command(self.CMD_VERTICAL_SCROLL, 0.1, "Set vertical scroll mode")

    def set_horizontal_scroll_mode(self) -> None:
        self._send_command(self.CMD_HORIZONTAL_SCROLL, 0.1, "Set horizontal scroll mode")

    # Font Selection Methods
    def set_international_font(self, font_id: int) -> None:
        cmd = self.CMD_INTERNATIONAL_FONT + bytes([font_id])
        self._send_command(cmd, 0.1, f"Set international font: {font_id}")

    def set_extended_font(self, font_id: int) -> None:
        cmd = self.CMD_EXTENDED_FONT + bytes([font_id])
        self._send_command(cmd, 0.1, f"Set extended font: {font_id}")

    # Display Control
    def display_on(self) -> None:
        self._send_command(self.CMD_DISPLAY_ON, 0.1, "Display on")

    def display_off(self) -> None:
        self._send_command(self.CMD_DISPLAY_OFF, 0.1, "Display off")

    # Manual ASCII Writing
    def write_at_cursor(self, text: str) -> None:
        """Write text at current cursor position (raw ASCII)"""
        self._send_command(text.encode('ascii', 'ignore'), 0.05, f"Write at cursor: '{text}'")

    # Comprehensive Test
    def test_display(self) -> None:
        logger.debug("Starting comprehensive display test")
        try:
            # Initialization
            self.initialize()
            self.clear_display()
            self.write_both_lines("DISPLAY TEST", "INITIALIZING...")
            time.sleep(1)
            
            # Brightness test
            for level in range(1, 5):
                self.set_brightness(level)
                self.write_upper_line(f"BRIGHTNESS: {level}/4")
                self.write_lower_line("TESTING...")
                time.sleep(1)
            
            # Cursor test
            self.clear_display()
            self.write_upper_line("CURSOR TEST")
            self.cursor_on()
            self.set_cursor_position(1, 2)
            time.sleep(1)
            self.set_cursor_position(10, 2)
            time.sleep(1)
            self.set_cursor_position(20, 2)
            time.sleep(1)
            self.cursor_off()
            
            # Scrolling test
            self.clear_display()
            self.write_upper_line("SCROLL TEST")
            self.scroll_lower_line("THIS IS A VERY LONG SCROLLING MESSAGE THAT EXCEEDS 20 CHARACTERS")
            time.sleep(5)
            
            # Mode test
            self.set_overwrite_mode()
            self.write_both_lines("OVERWRITE MODE", "ACTIVE")
            time.sleep(1)
            
            self.set_vertical_scroll_mode()
            self.write_both_lines("VERTICAL SCROLL", "MODE ACTIVE")
            time.sleep(1)
            
            self.set_horizontal_scroll_mode()
            self.write_both_lines("HORIZONTAL SCROLL", "MODE ACTIVE")
            time.sleep(1)
            
            # Completion
            self.set_overwrite_mode()
            self.clear_display()
            self.write_both_lines("TEST COMPLETE", "ALL SYSTEMS OK")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Test failed: {str(e)}")
            raise
        finally:
            self.clear_display()

    def close(self) -> None:
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
