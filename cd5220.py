"""
CD5220 VFD Display Control Library

Python interface for CD5220 VFD displays with smart mode management.
Supports string mode, continuous scrolling, and window-constrained viewport operations.
"""

try:  # use real pyserial if available
    import serial  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for test env
    from types import SimpleNamespace

    class SerialException(Exception):
        """Basic replacement for pyserial's SerialException."""
        pass

    class SerialTimeoutException(SerialException):
        """Timeout exception matching pyserial's interface."""
        pass

    class Serial:  # type: ignore
        def __init__(self, port, *args, **kwargs):
            raise SerialException(
                f"[Errno 2] could not open port {port}: [Errno 2] No such file or directory: '{port}'"
            )

    serial = SimpleNamespace(
        Serial=Serial,
        SerialException=SerialException,
        SerialTimeoutException=SerialTimeoutException,
    )
import time
import logging
import sys
from typing import Union, Optional, Dict, Any, Tuple, List, Iterator
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
            display.write_both_lines("Hello", "World")
            display.scroll_marquee("Scrolling text...")
    
    Hardware Compatibility:
        Most VFD displays work with zero delays (default). If your hardware 
        experiences dropped commands or mode transition failures, try:
        
        # Slow hardware compatibility
        display = CD5220('/dev/ttyUSB0', 
                        base_command_delay=0.01,      # 10ms between commands
                        mode_transition_delay=0.05)   # 50ms for mode changes
        
        # Per-command delay override
        display.set_brightness(3, delay=0.1)  # Force 100ms delay
    
    Mode Management:
    - NORMAL: Full cursor/ESC command support (default)
    - STRING: Fast line writing, limited to CLR/CAN commands
    - SCROLL: Continuous scrolling, limited to CLR/CAN commands  
    - VIEWPORT: Window-constrained display, limited to CLR/CAN commands
    """
    
    DISPLAY_WIDTH = 20
    DISPLAY_HEIGHT = 2

    # Hardware timing constants
    # SCROLL_REFRESH_RATE doesn't set anything, it's determined by hardware.
    # This value is just for calculating dependent timing elsewhere.
    SCROLL_REFRESH_RATE = 1.0  # Hz
    
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

    def __init__(self, serial_port: Union[str, serial.Serial, None] = None,
                 baudrate: int = 9600,
                 debug: bool = True,
                 auto_clear_mode_transitions: bool = True,
                 warn_on_mode_transitions: bool = True,
                 # Hardware compatibility delays (normally 0.0)
                 base_command_delay: float = 0.0,
                 mode_transition_delay: float = 0.0,
                 initialization_delay: float = 0.2,
                 enable_simulator: bool = True,
                 hardware_enabled: bool = True,
                 render_console: bool = False,
                 console_verbose: bool = False):
        """
        Initialize CD5220 controller.
        
        Args:
            serial_port: Serial port device, existing Serial object, or ``None`` for simulator-only mode
            baudrate: Communication baud rate (default 9600)
            debug: Enable debug logging
            auto_clear_mode_transitions: Auto-clear when mode conflicts occur
            warn_on_mode_transitions: Log warnings for mode transitions
            base_command_delay: Base delay between commands (seconds, default 0.0)
            mode_transition_delay: Delay for mode changes (seconds, default 0.0)
            initialization_delay: Delay for hardware initialization (seconds, default 0.2)
            enable_simulator: Create and maintain an in-memory simulator
            hardware_enabled: Attempt hardware connection when ``serial_port`` is provided
            render_console: Render simulator state to stdout after each command
            console_verbose: Show console output even when commands have no
                visible effect
        """
        self.debug = debug
        self.auto_clear_mode_transitions = auto_clear_mode_transitions
        self.warn_on_mode_transitions = warn_on_mode_transitions
        self.base_command_delay = base_command_delay
        self.mode_transition_delay = mode_transition_delay
        self.initialization_delay = initialization_delay
        self.render_console = render_console
        self.console_verbose = console_verbose
        self.simulator: Optional[DisplaySimulator] = DisplaySimulator() if enable_simulator or render_console else None
        self._first_console_render = True
        self._last_console_frame: Optional[Tuple[str, str]] = None
        self.hardware_enabled = False
        self._current_mode = DisplayMode.NORMAL
        # The hardware supports only one active window configuration
        # at a time, tracked as (line, start_col, end_col)
        self._active_window: Optional[Tuple[int, int, int]] = None
        # Simulator cursor position tracking (1-based)
        self._sim_x = 1
        self._sim_y = 1
        
        if debug:
            logger.setLevel(logging.DEBUG)
            logger.debug("Initializing CD5220 controller")
        
        try:
            if hardware_enabled and serial_port is not None:
                if isinstance(serial_port, str):
                    logger.debug(f"Opening serial port: {serial_port} at {baudrate} baud")
                    self.ser = serial.Serial(
                        port=serial_port,
                        baudrate=baudrate,
                        bytesize=8,
                        parity='N',
                        stopbits=1,
                        timeout=1,
                        write_timeout=1,
                    )
                else:
                    logger.debug("Using existing serial connection")
                    self.ser = serial_port
                self.hardware_enabled = True
                time.sleep(0.1)
                self._send_command(self.CMD_INITIALIZE, "Initialize display", self.initialization_delay)
                self.restore_defaults()
            else:
                self.ser = None
                if self.simulator:
                    self._parse_and_apply_command(self.CMD_INITIALIZE)
                    self._parse_and_apply_command(self.CMD_CLEAR)

        except (serial.SerialException, serial.SerialTimeoutException) as e:
            logger.error(f"Serial connection failed: {e}")
            raise CD5220DisplayError(f"Serial connection failed: {e}")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise CD5220DisplayError(f"Initialization failed: {e}")

    @classmethod
    def create_hardware_only(cls, port: str, **kwargs) -> "CD5220":
        """Factory for hardware-only operation."""
        return cls(port, enable_simulator=False, hardware_enabled=True, **kwargs)

    @classmethod
    def create_simulator_only(cls, **kwargs) -> "CD5220":
        """Factory for simulator-only operation."""
        return cls(None, enable_simulator=True, hardware_enabled=False, **kwargs)

    @classmethod
    def create_validation_mode(cls, port: str, **kwargs) -> "CD5220":
        """Factory for hardware + simulator validation mode."""
        return cls(port, enable_simulator=True, hardware_enabled=True, **kwargs)

    def _send_command(self, command: bytes, description: str = "Command", delay: float = None) -> None:
        """
        Send command with optional delay override.
        
        Args:
            command: Command bytes to send
            description: Debug description
            delay: Override delay (None = use base_command_delay, 0.0 = no delay)
        """
        try:
            if delay is None:
                delay = self.base_command_delay

            hex_str = ' '.join(f'{byte:02X}' for byte in command)
            logger.debug(f"Sending: {description} | Bytes: {hex_str} | Delay: {delay:.3f}s")

            if self.hardware_enabled and self.ser:
                self.ser.write(command)
                self.ser.flush()

            if self.simulator:
                before = self.simulator.get_display()
                self._parse_and_apply_command(command)
                after = self.simulator.get_display()
                if self.render_console:
                    changed = before != after
                    self._render_console_state(description, changed)

            if delay > 0:
                time.sleep(delay)
        except (serial.SerialException, serial.SerialTimeoutException) as e:
            logger.error(f"Command failed: {e}")
            raise CD5220DisplayError(f"Command failed: {e}")

    def _sync_simulator_mode(self) -> None:
        """Synchronize simulator mode with current hardware mode."""
        if self.simulator:
            self.simulator.set_mode(self._current_mode)
            if self._active_window is None:
                self.simulator.clear_window_state()
            else:
                self.simulator.set_window(*self._active_window)

    @property
    def current_mode(self) -> DisplayMode:
        """Get current display mode."""
        return self._current_mode

    @property
    def active_window(self) -> Optional[Tuple[int, int, int]]:
        """Return the currently configured window as (line, start, end)."""
        return self._active_window

    def get_display_info(self) -> Dict[str, Any]:
        """Return current display state information."""
        return {
            'mode': self.current_mode.value,
            'auto_clear': self.auto_clear_mode_transitions,
            'warn_transitions': self.warn_on_mode_transitions,
            'base_command_delay': self.base_command_delay,
            'mode_transition_delay': self.mode_transition_delay,
            'initialization_delay': self.initialization_delay,
            'active_window': self.active_window
        }

    # ------------------------------------------------------------------
    # Simulator helpers
    # ------------------------------------------------------------------

    def _parse_and_apply_command(self, command: bytes) -> None:
        """Mirror commands to the internal ``DisplaySimulator``."""
        if not self.simulator:
            return

        # ------------------------------------------------------------------
        # Display clearing and initialization
        # ------------------------------------------------------------------
        if command in (self.CMD_CLEAR, self.CMD_INITIALIZE):
            self.simulator.clear()
            self._sim_x = 1
            self._sim_y = 1
            self.simulator.set_mode(DisplayMode.NORMAL)
            self.simulator.clear_window_state()
            return

        if command == self.CMD_CANCEL:
            self.simulator.lines[self._sim_y - 1] = list(" " * self.DISPLAY_WIDTH)
            self._sim_x = 1
            self.simulator.set_mode(DisplayMode.NORMAL)
            self.simulator.viewport_buffer = ""
            return

        # ------------------------------------------------------------------
        # Fast string mode writes
        # ------------------------------------------------------------------
        if command.startswith(self.CMD_STRING_UPPER) and len(command) >= 24:
            text = command[len(self.CMD_STRING_UPPER):-1].decode('ascii', 'ignore')
            self.simulator.lines[0] = list(text.ljust(self.DISPLAY_WIDTH))
            self._sim_x = 1
            self._sim_y = 1
            self.simulator.set_mode(DisplayMode.STRING)
            return

        if command.startswith(self.CMD_STRING_LOWER) and len(command) >= 24:
            text = command[len(self.CMD_STRING_LOWER):-1].decode('ascii', 'ignore')
            self.simulator.lines[1] = list(text.ljust(self.DISPLAY_WIDTH))
            self._sim_x = 1
            self._sim_y = 2
            self.simulator.set_mode(DisplayMode.STRING)
            return

        # ------------------------------------------------------------------
        # Scroll mode writes (marquee)
        # ------------------------------------------------------------------
        if command.startswith(self.CMD_SCROLL_MARQUEE) and command.endswith(b"\x0D"):
            text = command[len(self.CMD_SCROLL_MARQUEE):-1].decode("ascii", "ignore")
            self.simulator.lines[0] = list(text.ljust(self.DISPLAY_WIDTH)[:self.DISPLAY_WIDTH])
            self.simulator.set_scroll_text(text)
            self._sim_x = 1
            self._sim_y = 1
            self.simulator.set_mode(DisplayMode.SCROLL)
            return

        # ------------------------------------------------------------------
        # Window management
        # ------------------------------------------------------------------
        if command.startswith(self.CMD_WINDOW_SET) and len(command) == 6:
            op = command[2]
            start = command[3] + 1
            end = command[4] + 1
            line = command[5]
            if op:
                self.simulator.set_window(line, start, end)
            else:
                self.simulator.clear_window_state()
            return

        # ------------------------------------------------------------------
        # Cursor movement and positioning
        # ------------------------------------------------------------------
        if command.startswith(self.CMD_CURSOR_POSITION) and len(command) == 4:
            self._sim_x = command[2]
            self._sim_y = command[3]
            return

        if command == self.CMD_CURSOR_HOME:
            self._sim_x = 1
            self._sim_y = 1
            return

        if command == self.CMD_CURSOR_LEFT and self._sim_x > 1:
            self._sim_x -= 1
            return

        if command == self.CMD_CURSOR_RIGHT and self._sim_x < self.DISPLAY_WIDTH:
            self._sim_x += 1
            return

        if command == self.CMD_CURSOR_UP and self._sim_y > 1:
            self._sim_y -= 1
            return

        if command == self.CMD_CURSOR_DOWN and self._sim_y < self.DISPLAY_HEIGHT:
            self._sim_y += 1
            return

        # ------------------------------------------------------------------
        # Display state commands
        # ------------------------------------------------------------------
        if command.startswith(self.CMD_BRIGHTNESS) and len(command) == 3:
            level = command[2]
            self.simulator.set_brightness_level(level)
            return

        if command == self.CMD_DISPLAY_ON:
            self.simulator.set_display_on(True)
            return

        if command == self.CMD_DISPLAY_OFF:
            self.simulator.set_display_on(False)
            return

        if command == self.CMD_CURSOR_ON:
            self.simulator.set_cursor_visible(True)
            return

        if command == self.CMD_CURSOR_OFF:
            self.simulator.set_cursor_visible(False)
            return

        # ------------------------------------------------------------------
        # Mode commands
        # ------------------------------------------------------------------
        if command == self.CMD_OVERWRITE_MODE:
            self.simulator.set_mode(DisplayMode.NORMAL)
            return

        if command == self.CMD_HORIZONTAL_SCROLL:
            # Actual target mode will be synced by high level API
            self.simulator.set_mode(DisplayMode.SCROLL)
            return

        if command == self.CMD_VERTICAL_SCROLL:
            self.simulator.set_mode(DisplayMode.SCROLL)
            return

        # ------------------------------------------------------------------
        # Printable text output
        # ------------------------------------------------------------------
        if all(32 <= b <= 126 for b in command):
            text = command.decode('ascii')
            for ch in text:
                if (
                    self.simulator.current_mode == DisplayMode.VIEWPORT
                    and self.simulator.active_window
                    and self._sim_y == self.simulator.active_window[0]
                ):
                    line, start, end = self.simulator.active_window
                    width = end - start + 1
                    self.simulator.viewport_buffer += ch
                    window_text = self.simulator.viewport_buffer[-width:]
                    padded = window_text.ljust(width)
                    for i, c in enumerate(padded):
                        self.simulator.set_char(start - 1 + i, line - 1, c)
                elif self.simulator.current_mode != DisplayMode.VIEWPORT:
                    self.simulator.set_char(self._sim_x - 1, self._sim_y - 1, ch)
                self._sim_x += 1
                if self._sim_x > self.DISPLAY_WIDTH:
                    self._sim_x = 1
                    if self._sim_y < self.DISPLAY_HEIGHT:
                        self._sim_y += 1
            return

    def _render_console_state(self, description: str, changed: bool) -> None:
        if not self.simulator:
            return
        line1, line2 = self.simulator.get_display()
        frame = (line1, line2)
        if not changed and not self.console_verbose:
            sys.stdout.write(f"[non-visual] {description}\n")
            sys.stdout.flush()
            return
        sep = "-" * self.DISPLAY_WIDTH
        if not changed:
            sys.stdout.write(f"[non-visual] {description}\n")
        if self._first_console_render:
            sys.stdout.write(sep + "\n")
            sys.stdout.write(line1 + "\n")
            sys.stdout.write(line2 + "\n")
            sys.stdout.write(sep + "\n")
            self._first_console_render = False
        else:
            sys.stdout.write("\x1b[4A")
            sys.stdout.write("\x1b[2K" + sep + "\n")
            sys.stdout.write("\x1b[2K" + line1 + "\n")
            sys.stdout.write("\x1b[2K" + line2 + "\n")
            sys.stdout.write("\x1b[2K" + sep + "\n")
        sys.stdout.flush()
        self._last_console_frame = frame

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

    def _send_cursor_position_raw(self, col: int, row: int, delay: float = None) -> None:
        """Send cursor position command without mode checking."""
        cmd = self.CMD_CURSOR_POSITION + bytes([col, row])
        self._send_command(cmd, f"Raw cursor: ({col},{row})", delay)

    def _write_text_raw(self, text: str, delay: float = None) -> None:
        """Send text without mode checking."""
        self._send_command(text.encode('ascii', 'ignore'), f"Raw write: '{text}'", delay)

    # === MODE CONTROL ===
    
    def clear_display(self, delay: float = None) -> None:
        """Clear display and return to normal mode."""
        self._send_command(self.CMD_CLEAR, "Clear display", delay)
        self._current_mode = DisplayMode.NORMAL
        self._active_window = None
        self._sync_simulator_mode()

    def cancel_current_line(self, delay: float = None) -> None:
        """Cancel current line and return to normal mode."""
        self._send_command(self.CMD_CANCEL, "Cancel current line", delay)
        self._current_mode = DisplayMode.NORMAL
        self._sync_simulator_mode()

    def initialize(self, delay: float = None) -> None:
        """Initialize display and return to normal mode."""
        init_delay = delay if delay is not None else self.initialization_delay
        self._send_command(self.CMD_INITIALIZE, "Initialize display", init_delay)
        self._send_command(self.CMD_CLEAR, "Clear after init", delay)
        self._current_mode = DisplayMode.NORMAL
        self._active_window = None
        self._sync_simulator_mode()

    def restore_defaults(self, delay: float = None) -> None:
        """Restore factory defaults: brightness 4, overwrite mode, cursor off."""
        self.clear_display(delay)
        self.set_brightness(4, delay)
        self.set_overwrite_mode(delay) 
        self.cursor_off(delay)

    # === NORMAL MODE METHODS ===
    
    def set_overwrite_mode(self, delay: float = None) -> None:
        """Set overwrite mode (normal mode only)."""
        self._ensure_normal_mode("Overwrite mode")
        mode_delay = delay if delay is not None else self.mode_transition_delay
        self._send_command(self.CMD_OVERWRITE_MODE, "Set overwrite mode", mode_delay)

    def set_vertical_scroll_mode(self, delay: float = None) -> None:
        """Set vertical scroll mode (normal mode only)."""
        self._ensure_normal_mode("Vertical scroll mode")
        mode_delay = delay if delay is not None else self.mode_transition_delay
        self._send_command(self.CMD_VERTICAL_SCROLL, "Set vertical scroll mode", mode_delay)

    def set_horizontal_scroll_mode(self, delay: float = None) -> None:
        """Set horizontal scroll mode (normal mode only)."""
        self._ensure_normal_mode("Horizontal scroll mode")
        mode_delay = delay if delay is not None else self.mode_transition_delay
        self._send_command(self.CMD_HORIZONTAL_SCROLL, "Set horizontal scroll mode", mode_delay)

    def set_brightness(self, level: int, delay: float = None) -> None:
        """
        Set display brightness (normal mode only).
        
        Args:
            level: Brightness level 1-4 (1=dimmest, 4=brightest)
            delay: Optional delay override (for slow hardware)
        """
        if not 1 <= level <= 4:
            raise CD5220DisplayError(f"Invalid brightness level: {level} (must be 1-4)")
        
        self._ensure_normal_mode("Brightness control")
        cmd = self.CMD_BRIGHTNESS + bytes([level])
        self._send_command(cmd, f"Set brightness: {level}", delay)

    def cursor_on(self, delay: float = None) -> None:
        """Enable cursor (normal mode only)."""
        self._ensure_normal_mode("Cursor control")
        self._send_command(self.CMD_CURSOR_ON, "Cursor on", delay)

    def cursor_off(self, delay: float = None) -> None:
        """Disable cursor (normal mode only)."""
        self._ensure_normal_mode("Cursor control")
        self._send_command(self.CMD_CURSOR_OFF, "Cursor off", delay)

    def set_cursor_position(self, col: int, row: int, delay: float = None) -> None:
        """
        Set cursor position (normal mode only).
        
        Args:
            col: Column 1-20
            row: Row 1-2
            delay: Optional delay override (for slow hardware)
        """
        if row not in (1, 2):
            raise CD5220DisplayError("Row must be 1 or 2")
        if not 1 <= col <= self.DISPLAY_WIDTH:
            raise CD5220DisplayError(f"Column must be 1-{self.DISPLAY_WIDTH}")
        
        self._ensure_normal_mode("Cursor positioning")
        self._send_cursor_position_raw(col, row, delay)

    def cursor_move_up(self, delay: float = None) -> None:
        """Move cursor up (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_UP, "Cursor up", delay)

    def cursor_move_down(self, delay: float = None) -> None:
        """Move cursor down (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_DOWN, "Cursor down", delay)

    def cursor_move_left(self, delay: float = None) -> None:
        """Move cursor left (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_LEFT, "Cursor left", delay)

    def cursor_move_right(self, delay: float = None) -> None:
        """Move cursor right (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_RIGHT, "Cursor right", delay)

    def cursor_home(self, delay: float = None) -> None:
        """Move cursor to home position (1,1) (normal mode only)."""
        self._ensure_normal_mode("Cursor movement")
        self._send_command(self.CMD_CURSOR_HOME, "Cursor home", delay)

    def write_at_cursor(self, text: str, delay: float = None) -> None:
        """Write text at current cursor position (normal mode only)."""
        self._ensure_normal_mode("Cursor writing")
        self._write_text_raw(text, delay)

    def write_positioned(self, text: str, col: int, row: int, delay: float = None) -> None:
        """Write text at specific position (normal mode only)."""
        self.set_cursor_position(col, row, delay)
        self.write_at_cursor(text, delay)

    def display_on(self, delay: float = None) -> None:
        """Turn display on (normal mode only)."""
        self._ensure_normal_mode("Display control")
        self._send_command(self.CMD_DISPLAY_ON, "Display on", delay)

    def display_off(self, delay: float = None) -> None:
        """Turn display off (normal mode only)."""
        self._ensure_normal_mode("Display control")
        self._send_command(self.CMD_DISPLAY_OFF, "Display off", delay)

    # === STRING MODE METHODS ===
    
    def write_upper_line(self, text: str, delay: float = None) -> None:
        """
        Write to upper line using fast string mode (ESC Q A).
        
        Enters STRING mode - only clear_display() or cancel_current_line() 
        will restore NORMAL mode functionality.
        
        Args:
            text: Text to display (truncated to 20 chars if longer)
            delay: Optional delay override (for slow hardware)
        """
        if len(text) > self.DISPLAY_WIDTH:
            text = text[:self.DISPLAY_WIDTH]
        padded_text = text.ljust(self.DISPLAY_WIDTH)
        cmd = self.CMD_STRING_UPPER + padded_text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, f"String upper: '{text}'", delay)
        self._current_mode = DisplayMode.STRING
        self._sync_simulator_mode()

    def write_lower_line(self, text: str, delay: float = None) -> None:
        """
        Write to lower line using fast string mode (ESC Q B).
        
        Args:
            text: Text to display (truncated to 20 chars if longer)
            delay: Optional delay override (for slow hardware)
        """
        if len(text) > self.DISPLAY_WIDTH:
            text = text[:self.DISPLAY_WIDTH]
        padded_text = text.ljust(self.DISPLAY_WIDTH)
        cmd = self.CMD_STRING_LOWER + padded_text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, f"String lower: '{text}'", delay)
        self._current_mode = DisplayMode.STRING
        self._sync_simulator_mode()

    def write_both_lines(self, upper: str, lower: str, delay: float = None) -> None:
        """
        Write to both lines using string mode.
        
        Args:
            upper: Text for upper line
            lower: Text for lower line
            delay: Optional delay override (for slow hardware)
        """
        self.write_upper_line(upper, delay)
        self.write_lower_line(lower, delay)

    # === CONTINUOUS SCROLLING METHODS ===
    
    def scroll_marquee(self, text: str, observe_duration: float = None, delay: float = None) -> None:
        """
        Start continuous marquee scrolling on upper line (ESC Q D).
        
        Hardware limitation: Upper line only.
        
        Args:
            text: Text to scroll
            observe_duration: Recommended viewing time
            delay: Optional delay override (for slow hardware)
        """
        cmd = self.CMD_SCROLL_MARQUEE + text.encode('ascii', 'ignore') + b'\x0D'
        self._send_command(cmd, f"Scroll marquee: '{text}'", delay)
        self._current_mode = DisplayMode.SCROLL
        self._sync_simulator_mode()
        
        if observe_duration is None:
            observe_duration = max(8.0, len(text) / self.SCROLL_REFRESH_RATE * 0.5)
        
        logger.info(f"Marquee scrolling for {observe_duration:.1f}s at ~{self.SCROLL_REFRESH_RATE}Hz")

    # === WINDOW MANAGEMENT METHODS ===
    
    def set_window(self, line: int, start_col: int, end_col: int, delay: float = None) -> None:
        """
        Set window range for viewport mode (normal mode only).
        
        Uses consistent 1-based indexing. Window boundaries match writing positions.

        Args:
            line: Line number (1 or 2)
            start_col: Starting column (1-20) - writing begins here
            end_col: Ending column (start_col to 20) - writing ends here
            delay: Optional delay override (for slow hardware)
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
        self._send_command(
            cmd,
            f"Set window: line {line}, cols {start_col}-{end_col}",
            delay,
        )
        self._active_window = (line, start_col, end_col)
        self._sync_simulator_mode()

    def clear_window(self, line: int = 1, delay: float = None) -> None:
        """Clear the active window (normal mode only)."""
        if line not in (1, 2):
            raise CD5220DisplayError("Line must be 1 or 2")

        self._ensure_normal_mode("Window management")

        cmd = self.CMD_WINDOW_SET + bytes([0, 0, 0, line])
        self._send_command(cmd, f"Clear window: line {line}", delay)

        self._active_window = None
        self._sync_simulator_mode()


    def enter_viewport_mode(self, delay: float = None) -> None:
        """
        Enter viewport mode for window-constrained display.
        
        Requires windows to be set first using set_window().
        
        Args:
            delay: Optional delay override (for slow hardware)
        """
        if self._active_window is None:
            raise CD5220DisplayError("No windows configured. Use set_window() first.")
        
        self._ensure_normal_mode("Viewport mode entry")
        self.set_horizontal_scroll_mode(delay)
        self._current_mode = DisplayMode.VIEWPORT
        self._sync_simulator_mode()
        
        logger.info(
            f"Entered viewport mode with window: line {self._active_window[0]},"
            f" cols {self._active_window[1]}-{self._active_window[2]}"
        )

    def write_viewport(
        self,
        line: int,
        text: str,
        char_delay: float = None,
        delay: float = None,
    ) -> None:
        """
        Write text to viewport window with optional smooth character building.
        
        Args:
            line: Line number (1 or 2)
            text: Text to write
            char_delay: If None, writes all text at once (fast).
                       If specified, writes character-by-character with delay (smooth building effect).
            delay: Optional delay override for positioning commands (for slow hardware)
        """
        if self._current_mode != DisplayMode.VIEWPORT:
            raise CD5220DisplayError("Must be in viewport mode. Use enter_viewport_mode() first.")
        
        if not self._active_window or self._active_window[0] != line:
            raise CD5220DisplayError(f"No window configured for line {line}")

        start_col, end_col = self._active_window[1], self._active_window[2]
        
        if char_delay is None:
            # Fast mode: write entire text at once (original behavior)
            self._send_cursor_position_raw(start_col, line, delay)
            self._write_text_raw(text, delay)
            logger.debug(f"Viewport write: line {line}, window {start_col}-{end_col}, text: '{text}'")
        else:
            # Smooth mode: character-by-character building with hardware cursor management
            self._send_cursor_position_raw(start_col, line, delay)
            logger.debug(f"Viewport incremental write: line {line}, window {start_col}-{end_col}, text: '{text}'")

            for char in text:
                self._write_text_raw(char, delay)
                time.sleep(char_delay)

    # === FONT CONTROL ===
    
    def set_international_font(self, font_id: int, delay: float = None) -> None:
        """Set international font (normal mode only)."""
        self._ensure_normal_mode("Font selection")
        cmd = self.CMD_INTERNATIONAL_FONT + bytes([font_id])
        self._send_command(cmd, f"Set international font: {font_id}", delay)

    def set_extended_font(self, font_id: int, delay: float = None) -> None:
        """Set extended font (normal mode only)."""
        self._ensure_normal_mode("Font selection")
        cmd = self.CMD_EXTENDED_FONT + bytes([font_id])
        self._send_command(cmd, f"Set extended font: {font_id}", delay)

    # === CONVENIENCE METHODS ===
    
    def display_message(self, message: str, duration: float = 2.0, mode: str = "string", delay: float = None) -> None:
        """
        Display a message with automatic line wrapping.
        
        Args:
            message: Message to display
            duration: How long to show the message
            mode: Display mode ("string" or "normal")
            delay: Optional delay override (for slow hardware)
        """
        lines = [message[i:i+self.DISPLAY_WIDTH] for i in range(0, len(message), self.DISPLAY_WIDTH)]
        
        if mode == "string":
            if len(lines) >= 1:
                self.write_upper_line(lines[0], delay)
            if len(lines) >= 2:
                self.write_lower_line(lines[1], delay)
        else:  # normal mode
            self.clear_display(delay)
            if len(lines) >= 1:
                self.write_positioned(lines[0], 1, 1, delay)
            if len(lines) >= 2:
                self.write_positioned(lines[1], 1, 2, delay)
        
        time.sleep(duration)

    def close(self) -> None:
        """Close serial connection."""
        if getattr(self, 'ser', None) is not None and self.ser.is_open:
            try:
                logger.debug("Closing serial connection")
                self.ser.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# ---------------------------------------------------------------------------
# Optional ASCII animation helpers
# ---------------------------------------------------------------------------

import math
import random
from typing import List, Iterator, Tuple, Optional


class DisplaySimulator:
    """In-memory model of the 2x20 display for testing animations."""

    def __init__(self) -> None:
        self.lines: List[List[str]] = [list(" " * 20), list(" " * 20)]
        self.frame_history: List[dict] = []
        self.current_mode: DisplayMode = DisplayMode.NORMAL
        self.active_window: Optional[Tuple[int, int, int]] = None
        self.scroll_text: Optional[str] = None
        self.viewport_buffer: str = ""
        self.brightness: int = 4
        self.display_on: bool = True
        self.cursor_visible: bool = False

    def clear(self) -> None:
        self.lines = [list(" " * 20), list(" " * 20)]
        self.viewport_buffer = ""

    def set_char(self, x: int, y: int, ch: str) -> None:
        if 0 <= x < 20 and 0 <= y < 2:
            self.lines[y][x] = ch

    def get_line(self, y: int) -> str:
        return "".join(self.lines[y])

    def get_display(self) -> Tuple[str, str]:
        return self.get_line(0), self.get_line(1)

    def apply_frame(self, line1: str, line2: str) -> None:
        old_state = self.get_display()
        lines = [line1.ljust(20), line2.ljust(20)]
        for y in range(2):
            for x in range(20):
                self.lines[y][x] = lines[y][x]
        changes = list(self.diff(lines))
        self.frame_history.append({
            'old_state': old_state,
            'new_state': self.get_display(),
            'changes': changes,
        })

    # --- state helpers ---
    def set_mode(self, mode: DisplayMode) -> None:
        self.current_mode = mode

    def set_window(self, line: int, start: int, end: int) -> None:
        self.active_window = (line, start, end)
        self.viewport_buffer = ""

    def clear_window_state(self) -> None:
        self.active_window = None
        self.viewport_buffer = ""

    def set_scroll_text(self, text: str) -> None:
        self.scroll_text = text

    def set_brightness_level(self, level: int) -> None:
        self.brightness = level

    def set_display_on(self, on: bool) -> None:
        self.display_on = on

    def set_cursor_visible(self, visible: bool) -> None:
        self.cursor_visible = visible

    def diff(self, new_lines: List[str]) -> Iterator[Tuple[int, int, str]]:
        for y in range(2):
            line = new_lines[y].ljust(20)
            for x, ch in enumerate(line):
                if self.lines[y][x] != ch:
                    yield x, y, ch

    # Assertion helpers for tests
    def assert_char_at(self, x: int, y: int, expected: str) -> None:
        actual = self.lines[y][x]
        assert actual == expected, f"Char at ({x},{y}) expected '{expected}', got '{actual}'"

    def assert_line_contains(self, line_num: int, text: str) -> None:
        line = self.get_line(line_num)
        assert text in line, f"Line {line_num} does not contain '{text}'"

    def assert_line_equals(self, line_num: int, expected: str) -> None:
        line = self.get_line(line_num).rstrip()
        expected = expected.ljust(20).rstrip()
        assert line == expected, (
            f"Line {line_num}: expected '{expected}', got '{line}'"
        )

    def assert_region_equals(self, x: int, y: int, width: int, expected: str) -> None:
        region = "".join(self.lines[y][x:x+width])
        assert region == expected, f"Region ({x},{y},{width}) expected '{expected}', got '{region}'"

    def assert_static_preserved(self, positions: List[Tuple[int, int, str]]) -> None:
        for x, y, char in positions:
            self.assert_char_at(x, y, char)

    def assert_brightness(self, level: int) -> None:
        assert self.brightness == level, (
            f"Brightness expected {level}, got {self.brightness}"
        )

    def assert_display_on(self, on: bool = True) -> None:
        assert self.display_on is on, (
            f"Display on expected {on}, got {self.display_on}"
        )

    def assert_cursor_visible(self, visible: bool = True) -> None:
        assert self.cursor_visible is visible, (
            f"Cursor visibility expected {visible}, got {self.cursor_visible}"
        )

    def dump(self) -> str:
        return f"Line 1: '{self.get_line(0)}'\nLine 2: '{self.get_line(1)}'"


class DiffAnimator:
    """Pure diff-based animator that only uses cursor positioning.

    When ``render_console`` is True, the internal ``DisplaySimulator`` is
    rendered to the terminal after each frame for visual debugging.
    """

    def __init__(
        self,
        display: 'CD5220',
        frame_rate: float = 4,
        sleep_fn: callable = time.sleep,
        frame_sleep_fn: callable = time.sleep,
        enable_simulator: bool = False,
        render_console: bool = False,
    ) -> None:
        """Create a new animator.

        Args:
            display: ``CD5220`` instance used for output
            frame_rate: Frames per second
            sleep_fn: General purpose sleep callback
            frame_sleep_fn: Sleep callback used between frames
            enable_simulator: Start with an attached ``DisplaySimulator``
            render_console: If True, render the simulator state to the
                terminal after each frame. Implies ``enable_simulator``.
        """
        self.display = display
        self.frame_rate = frame_rate
        self.sleep_fn = sleep_fn
        self.frame_sleep_fn = frame_sleep_fn
        self.buffer: List[List[str]] = [list(" " * 20), list(" " * 20)]
        self.state: List[List[str]] = [list(" " * 20), list(" " * 20)]
        self.render_console = render_console
        enable_simulator = enable_simulator or render_console
        self.simulator: Optional[DisplaySimulator] = DisplaySimulator() if enable_simulator else None
        self._first_console_render = True
        self.frame_buffer = self.buffer  # backward compatible attribute

    def sleep(self, seconds: float) -> None:
        if seconds > 0 and self.sleep_fn is not None:
            self.sleep_fn(seconds)

    def frame_sleep(self, seconds: float) -> None:
        if seconds > 0 and self.frame_sleep_fn is not None:
            self.frame_sleep_fn(seconds)

    def clear_buffer(self) -> None:
        self.buffer = [list(" " * 20), list(" " * 20)]
        self.frame_buffer = self.buffer

    def reset_tracking(self) -> None:
        self.state = [list(" " * 20), list(" " * 20)]
        self.frame_buffer = self.buffer

    def set_char(self, x: int, y: int, char: str) -> None:
        if 0 <= x < 20 and 0 <= y < 2:
            self.buffer[y][x] = char

    def render_frame(self) -> None:
        for y in range(2):
            for x in range(20):
                ch = self.buffer[y][x]
                if ch != self.state[y][x]:
                    self.display.write_positioned(ch, x + 1, y + 1)
                    self.state[y][x] = ch
                    if self.simulator:
                        self.simulator.set_char(x, y, ch)
        if self.render_console:
            self._render_console()

    def write_frame(self, line1: str, line2: str) -> None:
        lines = [line1.ljust(20), line2.ljust(20)]
        for y in range(2):
            for x in range(20):
                self.buffer[y][x] = lines[y][x]
        self.frame_buffer = self.buffer
        self.render_frame()

    def clear_display(self) -> None:
        self.display.clear_display()
        self.clear_buffer()
        self.reset_tracking()
        if self.simulator:
            self.simulator.clear()
        if self.render_console:
            self._first_console_render = True

    def get_simulator(self) -> Optional[DisplaySimulator]:
        """Return the attached DisplaySimulator, if enabled."""
        return self.simulator

    def enable_testing_mode(self) -> None:
        """Enable the internal DisplaySimulator for existing instances."""
        if self.simulator is None:
            self.simulator = DisplaySimulator()
            self.reset_tracking()

    def enable_console_render(self) -> None:
        """Enable console rendering of each frame using the simulator."""
        if not self.simulator:
            self.simulator = DisplaySimulator()
            self.reset_tracking()
        self.render_console = True

    def _render_console(self) -> None:
        """Render the simulator state to the terminal in-place."""
        if not self.simulator:
            return
        line1, line2 = self.simulator.get_display()
        sep = "-" * 20
        if self._first_console_render:
            sys.stdout.write(sep + "\n")
            sys.stdout.write(line1 + "\n")
            sys.stdout.write(line2 + "\n")
            sys.stdout.write(sep + "\n")
            self._first_console_render = False
        else:
            sys.stdout.write("\x1b[4A")
            sys.stdout.write("\x1b[2K" + sep + "\n")
            sys.stdout.write("\x1b[2K" + line1 + "\n")
            sys.stdout.write("\x1b[2K" + line2 + "\n")
            sys.stdout.write("\x1b[2K" + sep + "\n")
        sys.stdout.flush()




# Backwards compatibility alias
ASCIIAnimator = DiffAnimator


def bouncing_ball_animation(animator: DiffAnimator, duration: float = 10.0) -> None:
    """Bouncing ball using the pure write_frame approach."""
    ball_x, ball_y = 0, 0
    vel_x, vel_y = 1, 1
    frame_count = int(duration * animator.frame_rate)

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

    for _ in range(frame_count):
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
        animator.frame_sleep(1.0 / animator.frame_rate)


def progress_bar_animation(animator: DiffAnimator, duration: float = 8.0) -> None:
    """Animated progress bar using write_frame for each step."""
    steps = 10
    step_duration = duration / steps

    base_line1 = "LOADING    %        "
    base_line2 = "    [          ]    "
    animator.write_frame(base_line1, base_line2)

    for step in range(steps + 1):
        progress = step / steps
        filled = int(progress * 10)
        percentage = f"{int(progress * 100):03d}"

        line1_chars = list(base_line1)
        for i, ch in enumerate(percentage):
            line1_chars[8 + i] = ch
        line2_chars = list(base_line2)
        for i in range(10):
            line2_chars[5 + i] = '=' if i < filled else ' '

        animator.write_frame(''.join(line1_chars), ''.join(line2_chars))
        animator.frame_sleep(step_duration)

    animator.write_frame('     COMPLETE!      ', '    [==========]    ')


def spinning_loader(animator: DiffAnimator, duration: float = 6.0) -> None:
    """Spinner animation updating only the spinner character."""
    spinner_chars = ['|', '/', '-', '\\']
    frame_count = int(duration * animator.frame_rate)

    base_text = "  Processing "
    line1_base = base_text.ljust(20)
    line2 = "   Please wait...   "

    spinner_col = len(base_text)
    animator.write_frame(line1_base, line2)

    for frame in range(frame_count):
        chars = list(line1_base)
        chars[spinner_col] = spinner_chars[frame % len(spinner_chars)]
        animator.write_frame(''.join(chars), line2)
        animator.frame_sleep(1.0 / animator.frame_rate)

    animator.write_frame(line1_base, line2)


def wave_animation(animator: DiffAnimator, duration: float = 8.0) -> None:
    """Undulating wave pattern using write_frame."""
    frame_count = int(duration * animator.frame_rate)

    line1 = "~" * 20
    line2 = "~" * 20
    animator.write_frame(line1, line2)

    for frame in range(frame_count):
        phase = frame * 0.5
        line1_chars: List[str] = []
        line2_chars: List[str] = []
        for x in range(20):
            wave_val = math.sin((x + phase) * 0.3)
            if wave_val > 0.3:
                line1_chars.append('^')
                line2_chars.append(' ')
            elif wave_val < -0.3:
                line1_chars.append(' ')
                line2_chars.append('v')
            else:
                line1_chars.append('~')
                line2_chars.append('~')
        animator.write_frame(''.join(line1_chars), ''.join(line2_chars))
        animator.frame_sleep(1.0 / animator.frame_rate)


def matrix_rain_animation(animator: DiffAnimator, duration: float = 12.0) -> None:
    columns = []
    for _ in range(20):
        columns.append({'chars': [], 'next_spawn': random.randint(0, 10)})

    frame_count = int(duration * animator.frame_rate)
    chars = '01ABCDEF'

    animator.write_frame(' ' * 20, ' ' * 20)

    for _ in range(frame_count):
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


def typewriter_animation(animator: DiffAnimator, text: str, line: int = 0) -> None:
    row = 0 if line == 0 else 1
    for i, ch in enumerate(text):
        animator.display.write_positioned(ch, i + 1, row + 1)
        animator.sleep(0.1)

    cursor_col = len(text) + 1
    for blink in range(6):
        cursor = '_' if blink % 2 == 0 else ' '
        animator.display.write_positioned(cursor, cursor_col, row + 1)
        animator.frame_sleep(0.3)


def pulsing_alert(animator: DiffAnimator, message: str, duration: float = 6.0) -> None:
    """Pulse brightness while keeping text static."""
    pulse_count = int(duration * 2)
    centered = message.center(20)
    animator.write_frame(centered, centered)
    for pulse in range(pulse_count):
        brightness = 4 if pulse % 2 == 0 else 1
        animator.display.set_brightness(brightness)
        animator.frame_sleep(0.5)
    animator.display.set_brightness(4)


class CD5220ASCIIAnimations:
    """High level ASCII animation wrapper."""

    def __init__(
        self,
        display: 'CD5220',
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

    def bouncing_ball_animation(self, duration: float = 10.0) -> None:
        bouncing_ball_animation(self.animator, duration)

    def progress_bar_animation(self, duration: float = 8.0) -> None:
        progress_bar_animation(self.animator, duration)

    def spinning_loader(self, duration: float = 6.0) -> None:
        spinning_loader(self.animator, duration)

    def wave_animation(self, duration: float = 8.0) -> None:
        wave_animation(self.animator, duration)

    def matrix_rain_animation(self, duration: float = 12.0) -> None:
        matrix_rain_animation(self.animator, duration)

    def typewriter_animation(self, text: str, line: int = 0) -> None:
        typewriter_animation(self.animator, text, line)

    def pulsing_alert(self, message: str, duration: float = 6.0) -> None:
        pulsing_alert(self.animator, message, duration)

    def get_simulator(self) -> Optional[DisplaySimulator]:
        """Return the internal DisplaySimulator if enabled."""
        return self.animator.simulator

    def enable_testing_mode(self) -> None:
        """Enable simulator-based testing."""
        self.animator.enable_testing_mode()

    def play_startup_sequence(self) -> None:
        self.typewriter_animation("CD5220 STARTING...", line=0)
        self.animator.frame_sleep(1)

        # ensure blank screen before progress bar
        self.animator.clear_display()
        self.progress_bar_animation(duration=4)
        self.animator.frame_sleep(0.5)

        # clear before matrix rain
        self.animator.clear_display()
        self.matrix_rain_animation(duration=3)

        # clear before ready alert
        self.animator.clear_display()
        self.pulsing_alert("READY!", duration=2)

        # leave the display cleared for next use
        self.animator.clear_display()

    def play_demo_cycle(self) -> None:
        animations = [
            ("Bouncing Ball", lambda: self.bouncing_ball_animation(duration=5)),
            ("Wave Motion", lambda: self.wave_animation(duration=5)),
            ("Matrix Rain", lambda: self.matrix_rain_animation(duration=5)),
            ("Spinner", lambda: self.spinning_loader(duration=3)),
            ("Progress Bar", lambda: self.progress_bar_animation(duration=4)),
        ]
        for name, func in animations:
            # Clear any remnants from previous animation
            self.animator.clear_display()

            # Show animation title briefly
            self.typewriter_animation(name, line=0)
            self.animator.frame_sleep(1)

            # Start animation on a blank screen for visual clarity
            self.animator.clear_display()
            func()
            self.animator.frame_sleep(1)

    def play_error_alert(self, error_message: str) -> None:
        for flash in range(6):
            if flash % 2 == 0:
                border = '*' * 20
                self.display.write_both_lines(border, border)
            else:
                centered = error_message[:18].center(20)
                self.display.write_both_lines(centered, ' ' * 20)
            self.animator.frame_sleep(0.3)
        self.pulsing_alert(error_message[:20], duration=3)

