"""
CD5220 Library Unit Tests

Mock-based unit tests that validate library functionality without requiring
actual hardware. These tests focus on parameter validation, state management,
window management, and error handling.
"""

import pytest
from cd5220 import serial
import time
from unittest.mock import Mock, patch, MagicMock
from cd5220 import CD5220, DisplayMode, CD5220DisplayError, DiffAnimator

class TestCD5220Unit:
    """Unit tests for CD5220 library without hardware dependencies."""

    @pytest.fixture
    def mock_display(self):
        """Create a CD5220 instance with mocked serial connection."""
        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            display = CD5220('mock_port', debug=False)
            display.ser = mock_serial.return_value
            return display

    def test_initialization_parameters(self, mock_display):
        """Test initialization with various parameters."""
        assert mock_display.current_mode == DisplayMode.NORMAL
        assert mock_display.auto_clear_mode_transitions == True
        assert mock_display.warn_on_mode_transitions == True
        assert mock_display.base_command_delay == 0.0
        assert mock_display.mode_transition_delay == 0.0
        assert mock_display.initialization_delay == 0.2
        assert mock_display.active_window is None

    def test_custom_initialization_parameters(self):
        """Test initialization with custom delay parameters."""
        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            display = CD5220('mock_port',
                            debug=False,
                            base_command_delay=0.01,
                            mode_transition_delay=0.05,
                            initialization_delay=0.5)
            assert display.base_command_delay == 0.01
            assert display.mode_transition_delay == 0.05
            assert display.initialization_delay == 0.5

    def test_brightness_parameter_validation(self, mock_display):
        """Test brightness parameter validation."""
        # Valid brightness levels
        for level in range(1, 5):
            mock_display.set_brightness(level)  # Should not raise

        # Invalid brightness levels
        with pytest.raises(CD5220DisplayError, match="Invalid brightness level"):
            mock_display.set_brightness(0)

        with pytest.raises(CD5220DisplayError, match="Invalid brightness level"):
            mock_display.set_brightness(5)

        with pytest.raises(CD5220DisplayError, match="Invalid brightness level"):
            mock_display.set_brightness(-1)

    def test_cursor_position_validation(self, mock_display):
        """Test cursor position parameter validation."""
        # Valid positions
        mock_display.set_cursor_position(1, 1)
        mock_display.set_cursor_position(20, 2)
        mock_display.set_cursor_position(10, 1)

        # Invalid rows
        with pytest.raises(CD5220DisplayError, match="Row must be 1 or 2"):
            mock_display.set_cursor_position(1, 0)

        with pytest.raises(CD5220DisplayError, match="Row must be 1 or 2"):
            mock_display.set_cursor_position(1, 3)

        # Invalid columns
        with pytest.raises(CD5220DisplayError, match="Column must be 1-20"):
            mock_display.set_cursor_position(0, 1)

        with pytest.raises(CD5220DisplayError, match="Column must be 1-20"):
            mock_display.set_cursor_position(21, 1)

    def test_delay_parameter_positioning(self, mock_display):
        """Test that delay parameters are properly positioned at the end of argument lists."""
        # Test methods with delay parameter at the end
        mock_display.set_brightness(3, delay=0.1)
        mock_display.set_cursor_position(1, 1, delay=0.05)
        mock_display.write_upper_line("TEST", delay=0.02)
        mock_display.write_lower_line("TEST", delay=0.02)
        mock_display.write_both_lines("UP", "DOWN", delay=0.02)
        mock_display.clear_display(delay=0.01)
        mock_display.set_window(1, 5, 15, delay=0.03)

        # Set up viewport mode for write_viewport test
        mock_display.enter_viewport_mode()
        mock_display.write_viewport(1, "TEST", char_delay=0.1, delay=0.02)

        # These should all work without raising exceptions
        assert True

    def test_mode_state_tracking(self, mock_display):
        """Test mode state tracking including viewport mode."""
        # Start in normal mode
        assert mock_display.current_mode == DisplayMode.NORMAL

        # Transition to string mode
        mock_display.write_upper_line("TEST")
        assert mock_display.current_mode == DisplayMode.STRING

        # Transition to scroll mode
        mock_display.scroll_marquee("SCROLL TEST")
        assert mock_display.current_mode == DisplayMode.SCROLL

        # Return to normal via clear
        mock_display.clear_display()
        assert mock_display.current_mode == DisplayMode.NORMAL

        # Test viewport mode
        mock_display.set_window(1, 5, 15)
        mock_display.enter_viewport_mode()
        assert mock_display.current_mode == DisplayMode.VIEWPORT

        # Return to normal via cancel
        mock_display.cancel_current_line()
        assert mock_display.current_mode == DisplayMode.NORMAL

    def test_window_management_1_based_indexing(self, mock_display):
        """Test window management with 1-based indexing consistency."""
        # Test valid window setting with 1-based coordinates
        mock_display.set_window(1, 5, 15)
        assert mock_display.active_window == (1, 5, 15)

        mock_display.set_window(2, 3, 18)
        assert mock_display.active_window == (2, 3, 18)

        # Test edge cases for 1-based indexing
        mock_display.set_window(1, 1, 20)  # Full width window
        assert mock_display.active_window == (1, 1, 20)

        mock_display.set_window(2, 10, 10)  # Single character window
        assert mock_display.active_window == (2, 10, 10)

        # Test window parameter validation
        with pytest.raises(CD5220DisplayError, match="Line must be 1 or 2"):
            mock_display.set_window(3, 5, 15)

        with pytest.raises(CD5220DisplayError, match="Invalid window range"):
            mock_display.set_window(1, 15, 5)  # start > end

        with pytest.raises(CD5220DisplayError, match="Invalid window range"):
            mock_display.set_window(1, 0, 10)  # start < 1 (not 1-based)

        with pytest.raises(CD5220DisplayError, match="Invalid window range"):
            mock_display.set_window(1, 5, 25)  # end > 20

        # Test window clearing
        mock_display.clear_window(1)
        assert mock_display.active_window is None

    def test_consolidated_viewport_writing(self, mock_display):
        """Test consolidated write_viewport method with optional char_delay."""
        # Setup viewport
        mock_display.set_window(1, 5, 15)
        mock_display.enter_viewport_mode()

        # Test fast writing (no delay)
        mock_display.write_viewport(1, "FAST_TEXT")  # Should not raise

        # Test incremental writing (with delay) - mock _send_command to avoid internal sleeps
        with patch('time.sleep') as mock_sleep, \
             patch.object(mock_display, '_send_command') as mock_send_command:
            mock_display.write_viewport(1, "SLOW", char_delay=0.1)
            # Should have called sleep for each character
            assert mock_sleep.call_count == 4  # "SLOW" = 4 characters
            # Verify sleep was called with correct delay
            mock_sleep.assert_called_with(0.1)

    def test_viewport_mode_requirements(self, mock_display):
        """Test viewport mode entry requirements."""
        # Should fail without windows
        with pytest.raises(CD5220DisplayError, match="No windows configured"):
            mock_display.enter_viewport_mode()

        # Should work with windows
        mock_display.set_window(1, 5, 15)
        mock_display.enter_viewport_mode()
        assert mock_display.current_mode == DisplayMode.VIEWPORT

        # Test viewport writing requirements
        with pytest.raises(CD5220DisplayError, match="No window configured for line 2"):
            mock_display.write_viewport(2, "TEST")

        # Should work for configured line (both fast and incremental)
        mock_display.write_viewport(1, "TEST")  # Fast mode
        with patch.object(mock_display, '_send_command'):
            mock_display.write_viewport(1, "TEST", char_delay=0.1)  # Incremental mode

        # Test mode requirement for viewport writing
        mock_display.clear_display()  # Exit viewport mode
        with pytest.raises(CD5220DisplayError, match="Must be in viewport mode"):
            mock_display.write_viewport(1, "TEST")

    def test_auto_clear_mode_transitions(self, mock_display):
        """Test automatic mode transitions."""
        # Enable auto-clear
        mock_display.auto_clear_mode_transitions = True

        # Go to string mode
        mock_display.write_upper_line("STRING MODE")
        assert mock_display.current_mode == DisplayMode.STRING

        # Normal mode operation should auto-clear
        mock_display.set_brightness(3)
        assert mock_display.current_mode == DisplayMode.NORMAL

        # Test viewport mode auto-clear
        mock_display.set_window(1, 5, 15)
        mock_display.enter_viewport_mode()
        assert mock_display.current_mode == DisplayMode.VIEWPORT

        # Should auto-clear from viewport mode too
        mock_display.cursor_on()
        assert mock_display.current_mode == DisplayMode.NORMAL
        assert mock_display.active_window is None  # Window should be cleared

    def test_manual_mode_control_disabled(self, mock_display):
        """Test manual mode control when auto-clear is disabled."""
        # Disable auto-clear
        mock_display.auto_clear_mode_transitions = False
        mock_display.warn_on_mode_transitions = True

        # Go to string mode
        mock_display.write_upper_line("STRING MODE")
        assert mock_display.current_mode == DisplayMode.STRING

        # Normal mode operation should fail
        with pytest.raises(CD5220DisplayError, match="requires normal mode"):
            mock_display.set_brightness(3)

        # Manual clear should work
        mock_display.clear_display()
        assert mock_display.current_mode == DisplayMode.NORMAL
        mock_display.set_brightness(3)  # Should work now

    def test_string_mode_text_handling(self, mock_display):
        """Test string mode text processing."""
        # Test normal text
        mock_display.write_upper_line("NORMAL TEXT")

        # Test long text (should be truncated)
        long_text = "A" * 25  # Exceeds 20 characters
        mock_display.write_upper_line(long_text)

        # Test empty text
        mock_display.write_upper_line("")

        # Verify state is STRING after all operations
        assert mock_display.current_mode == DisplayMode.STRING

    def test_display_info_method(self, mock_display):
        """Test display info reporting."""
        info = mock_display.get_display_info()

        expected_keys = [
            'mode',
            'auto_clear',
            'warn_transitions',
            'base_command_delay',
            'mode_transition_delay',
            'initialization_delay',
            'active_window',
        ]
        for key in expected_keys:
            assert key in info

        assert info['mode'] == 'normal'
        assert isinstance(info['auto_clear'], bool)
        assert isinstance(info['warn_transitions'], bool)
        assert isinstance(info['base_command_delay'], float)
        assert isinstance(info['mode_transition_delay'], float)
        assert isinstance(info['initialization_delay'], float)
        assert info['active_window'] is None or isinstance(info['active_window'], tuple)

    def test_restore_defaults_method(self, mock_display):
        """Test restore_defaults method with correct state management."""
        # Change state - write_upper_line sets mode to STRING
        mock_display.write_upper_line("TEST")
        assert mock_display.current_mode == DisplayMode.STRING

        # set_window requires normal mode, so it auto-clears and mode becomes NORMAL
        mock_display.set_window(1, 5, 15)
        assert mock_display.current_mode == DisplayMode.NORMAL  # Mode is now NORMAL due to auto-clear
        assert mock_display.active_window is not None  # Window was configured

        # Restore defaults should clear everything
        mock_display.restore_defaults()
        assert mock_display.current_mode == DisplayMode.NORMAL
        assert mock_display.active_window is None

    def test_send_command_delay_override(self, mock_display):
        """Test _send_command delay override system."""
        with patch('time.sleep') as mock_sleep:
            # Test default delay (should be 0.0)
            mock_display._send_command(b'test', "Test command")
            mock_sleep.assert_not_called()  # No sleep for 0.0 delay

            # Test explicit delay override
            mock_display._send_command(b'test', "Test command", delay=0.1)
            mock_sleep.assert_called_once_with(0.1)

            # Reset mock
            mock_sleep.reset_mock()

            # Test with display that has non-zero base delay
            mock_display.base_command_delay = 0.05
            mock_display._send_command(b'test', "Test command")
            mock_sleep.assert_called_once_with(0.05)

    def test_mode_transition_delays(self, mock_display):
        """Test mode transition delay system."""
        # Set custom mode transition delay
        mock_display.mode_transition_delay = 0.1

        with patch('time.sleep') as mock_sleep:
            # Mode transition methods should use mode_transition_delay
            mock_display.set_overwrite_mode()
            mock_sleep.assert_called_with(0.1)

            # Reset mock
            mock_sleep.reset_mock()

            # Override should work
            mock_display.set_vertical_scroll_mode(delay=0.2)
            mock_sleep.assert_called_with(0.2)

    def test_convenience_methods_updated(self, mock_display):
        """Test convenience methods including updated viewport functionality."""
        # Test display_message method with delay parameter
        mock_display.display_message("TEST MESSAGE", duration=0.1, delay=0.05)
        assert mock_display.current_mode == DisplayMode.STRING

        # Test manual viewport setup with incremental writing
        mock_display.clear_display()
        mock_display.set_window(1, 5, 15)
        mock_display.enter_viewport_mode()

        # Test both fast and incremental writing with delay overrides
        mock_display.write_viewport(1, "FAST", delay=0.01)  # Fast mode with command delay

        # Mock _send_command to avoid internal sleep calls interfering with test
        with patch('time.sleep') as mock_sleep, \
             patch.object(mock_display, '_send_command') as mock_send_command:
            mock_display.write_viewport(1, "SLOW", char_delay=0.1, delay=0.02)  # Incremental mode
            assert mock_sleep.call_count == 4  # 4 characters

    def test_context_manager(self):
        """Test context manager functionality."""
        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True

            with CD5220('mock_port') as display:
                assert display.ser.is_open
                display.write_upper_line("CONTEXT TEST")

            # Verify close was called
            mock_serial.return_value.close.assert_called_once()

    def test_mode_isolation_after_operations(self, mock_display):
        """Test that operations don't leave the display in unexpected states."""
        # Test that string operations can be cleanly reset
        mock_display.write_upper_line("TEST STRING")
        assert mock_display.current_mode == DisplayMode.STRING

        mock_display.clear_display()
        assert mock_display.current_mode == DisplayMode.NORMAL
        assert mock_display.active_window is None

    def test_render_console_state_outputs(self, mock_display, capsys):
        anim = DiffAnimator(
            mock_display,
            enable_simulator=True,
            render_console=True,
            sleep_fn=lambda _: None,
            frame_sleep_fn=lambda _: None,
        )
        anim.write_frame("HELLO", "WORLD")
        out = capsys.readouterr().out
        assert "HELLO" in out

    def test_ensure_normal_mode_auto_clears(self, mock_display):
        mock_display._current_mode = DisplayMode.STRING
        cleared = mock_display._ensure_normal_mode("write")
        assert cleared is True
        assert mock_display.current_mode == DisplayMode.NORMAL

    def test_init_with_existing_serial(self):
        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            existing = mock_serial.return_value
            display = CD5220(existing, debug=False)
            assert display.ser is existing
            assert display.hardware_enabled is True

    def test_render_console_state_verbose(self, capsys):
        display = CD5220(debug=False, enable_simulator=True, render_console=True)
        display._render_console_state("desc", True)
        out = capsys.readouterr().out
        assert "desc" in out or out

    def test_cursor_movement_commands(self, mock_display):
        """Cursor movement helpers update simulator coordinates."""
        mock_display.cursor_move_right()
        assert mock_display._sim_x == 2
        mock_display.cursor_move_down()
        assert mock_display._sim_y == 2
        mock_display.cursor_move_left()
        assert mock_display._sim_x == 1
        mock_display.cursor_move_up()
        assert mock_display._sim_y == 1

    def test_ensure_normal_mode_errors_when_disabled(self):
        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            disp = CD5220('mock', debug=False, auto_clear_mode_transitions=False)
            disp.ser = mock_serial.return_value
            disp._current_mode = DisplayMode.STRING
            with pytest.raises(CD5220DisplayError):
                disp._ensure_normal_mode('write')


class TestCD5220ErrorHandling:
    """Test error handling scenarios."""

    def test_serial_connection_failure(self):
        """Test handling of serial connection failures."""
        with patch('cd5220.serial.Serial', side_effect=serial.SerialException("Connection failed")):
            with pytest.raises(CD5220DisplayError, match="Serial connection failed"):
                CD5220('invalid_port')

    def test_command_transmission_failure_during_init(self):
        """Test handling of command transmission failures during initialization."""
        with patch('cd5220.serial.Serial') as mock_serial:
            # Set up the mock to succeed for connection but fail for write
            mock_instance = MagicMock()
            mock_instance.write.side_effect = serial.SerialException("Write failed")
            mock_serial.return_value = mock_instance

            with pytest.raises(CD5220DisplayError, match="Initialization failed"):
                CD5220('mock_port')

    def test_command_transmission_failure_after_init(self):
        """Test handling of command transmission failures after initialization."""
        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            display = CD5220('mock_port', debug=False)

            # Now make write fail
            display.ser.write.side_effect = serial.SerialException("Write failed")

            with pytest.raises(CD5220DisplayError, match="Command failed"):
                display._send_command(b'test')

    def test_viewport_error_conditions(self):
        """Test specific viewport mode error conditions."""
        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            display = CD5220('mock_port', debug=False)

            # Test writing to viewport without being in viewport mode
            display.set_window(1, 5, 15)
            with pytest.raises(CD5220DisplayError, match="Must be in viewport mode"):
                display.write_viewport(1, "TEST")

            # Test entering viewport mode without windows
            display.clear_window()
            with pytest.raises(CD5220DisplayError, match="No windows configured"):
                display.enter_viewport_mode()


class TestCD5220Simulator:
    """Tests for the built-in simulator functionality."""

    def test_default_simulator_creation(self):
        display = CD5220(debug=False)
        assert display.simulator is not None

        display.clear_display()
        sim = display.simulator
        assert sim.get_line(1).strip() == ""

    def test_factory_helpers(self):
        sim_only = CD5220.create_simulator_only(debug=False)
        assert sim_only.hardware_enabled is False
        assert sim_only.simulator is not None

        with patch('cd5220.serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            hw_only = CD5220.create_hardware_only('port', debug=False)
            assert hw_only.simulator is None

            validation = CD5220.create_validation_mode('port', debug=False)
            assert validation.simulator is not None

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
