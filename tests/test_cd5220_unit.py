"""
CD5220 Library Unit Tests

Mock-based unit tests that validate library functionality without requiring
actual hardware. These tests focus on parameter validation, state management,
and error handling.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from cd5220 import CD5220, DisplayMode, CD5220DisplayError

class TestCD5220Unit:
    """Unit tests for CD5220 library without hardware dependencies."""
    
    @pytest.fixture
    def mock_display(self):
        """Create a CD5220 instance with mocked serial connection."""
        with patch('serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            display = CD5220('mock_port', debug=False)
            display.ser = mock_serial.return_value
            return display
    
    def test_initialization_parameters(self, mock_display):
        """Test initialization with various parameters."""
        assert mock_display.current_mode == DisplayMode.NORMAL
        assert mock_display.auto_clear_mode_transitions == True
        assert mock_display.warn_on_mode_transitions == True
        assert mock_display.default_delay == 0.05
        assert mock_display.bulk_multiplier == 2.0
    
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
    
    def test_mode_state_tracking(self, mock_display):
        """Test mode state tracking."""
        # Start in normal mode
        assert mock_display.current_mode == DisplayMode.NORMAL
        
        # Transition to string mode
        mock_display.write_upper_line_string("TEST")
        assert mock_display.current_mode == DisplayMode.STRING
        
        # Transition to scroll mode
        mock_display.scroll_upper_line("SCROLL TEST")
        assert mock_display.current_mode == DisplayMode.SCROLL
        
        # Return to normal via clear
        mock_display.clear_display()
        assert mock_display.current_mode == DisplayMode.NORMAL
        
        # Return to normal via cancel
        mock_display.write_lower_line_string("TEST")
        assert mock_display.current_mode == DisplayMode.STRING
        mock_display.cancel_current_line()
        assert mock_display.current_mode == DisplayMode.NORMAL
    
    def test_auto_clear_mode_transitions(self, mock_display):
        """Test automatic mode transitions."""
        # Enable auto-clear
        mock_display.auto_clear_mode_transitions = True
        
        # Go to string mode
        mock_display.write_upper_line_string("STRING MODE")
        assert mock_display.current_mode == DisplayMode.STRING
        
        # Normal mode operation should auto-clear
        mock_display.set_brightness(3)
        assert mock_display.current_mode == DisplayMode.NORMAL
    
    def test_manual_mode_control_disabled(self, mock_display):
        """Test manual mode control when auto-clear is disabled."""
        # Disable auto-clear
        mock_display.auto_clear_mode_transitions = False
        mock_display.warn_on_mode_transitions = True
        
        # Go to string mode
        mock_display.write_upper_line_string("STRING MODE")
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
        mock_display.write_upper_line_string("NORMAL TEXT")
        
        # Test long text (should be truncated)
        long_text = "A" * 25  # Exceeds 20 characters
        mock_display.write_upper_line_string(long_text)
        
        # Test empty text
        mock_display.write_upper_line_string("")
        
        # Verify state is STRING after all operations
        assert mock_display.current_mode == DisplayMode.STRING
    
    def test_display_info_method(self, mock_display):
        """Test display info reporting."""
        info = mock_display.get_display_info()
        
        expected_keys = ['mode', 'auto_clear', 'warn_transitions', 'default_delay', 'bulk_multiplier']
        for key in expected_keys:
            assert key in info
        
        assert info['mode'] == 'normal'
        assert isinstance(info['auto_clear'], bool)
        assert isinstance(info['warn_transitions'], bool)
        assert isinstance(info['default_delay'], float)
        assert isinstance(info['bulk_multiplier'], float)
    
    def test_restore_defaults_method(self, mock_display):
        """Test restore_defaults method."""
        # Change state
        mock_display.write_upper_line_string("TEST")
        assert mock_display.current_mode == DisplayMode.STRING
        
        # Restore defaults
        mock_display.restore_defaults()
        assert mock_display.current_mode == DisplayMode.NORMAL
    
    def test_configurable_timing(self, mock_display):
        """Test configurable timing system."""
        # Test default timing
        assert mock_display.default_delay == 0.05
        assert mock_display.bulk_multiplier == 2.0
        
        # Create display with custom timing
        with patch('serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            custom_display = CD5220('mock_port', command_delay=0.1, bulk_delay_multiplier=3.0)
            assert custom_display.default_delay == 0.1
            assert custom_display.bulk_multiplier == 3.0
    
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_command_delay_calculation(self, mock_sleep, mock_display):
        """Test adaptive command delay calculation."""
        # Short command should use default delay
        mock_display._send_command(b'short', description="Short command")
        
        # Long command should use scaled delay
        long_command = b'A' * 40  # 40 bytes
        mock_display._send_command(long_command, description="Long command")
        
        # Verify sleep was called (timing validated by the mock)
        assert mock_sleep.call_count >= 2
    
    def test_legacy_compatibility_methods(self, mock_display):
        """Test legacy compatibility methods."""
        # Legacy methods should work and set correct mode
        mock_display.write_upper_line("LEGACY UPPER")
        assert mock_display.current_mode == DisplayMode.STRING
        
        mock_display.clear_display()
        mock_display.write_lower_line("LEGACY LOWER")
        assert mock_display.current_mode == DisplayMode.STRING
        
        mock_display.clear_display()
        mock_display.write_both_lines("LEGACY 1", "LEGACY 2")
        assert mock_display.current_mode == DisplayMode.STRING
    
    def test_context_manager(self):
        """Test context manager functionality."""
        with patch('serial.Serial') as mock_serial:
            mock_serial.return_value.is_open = True
            
            with CD5220('mock_port') as display:
                assert display.ser.is_open
                display.write_upper_line_string("CONTEXT TEST")
            
            # Verify close was called
            mock_serial.return_value.close.assert_called_once()

class TestCD5220ErrorHandling:
    """Test error handling scenarios."""
    
    def test_serial_connection_failure(self):
        """Test handling of serial connection failures."""
        with patch('serial.Serial', side_effect=Exception("Connection failed")):
            with pytest.raises(CD5220DisplayError, match="Serial connection failed"):
                CD5220('invalid_port')
    
    def test_command_transmission_failure(self):
        """Test handling of command transmission failures."""
        with patch('serial.Serial') as mock_serial:
            mock_serial.return_value.write.side_effect = Exception("Write failed")
            
            with pytest.raises(CD5220DisplayError, match="Command failed"):
                display = CD5220('mock_port')
                display._send_command(b'test')

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
