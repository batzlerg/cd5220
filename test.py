#!/usr/bin/env python3
"""
CD5220 VFD Display Comprehensive Test Suite with Smart Mode Management

Demonstrates all documented modes and the smart mode management system:
- Normal Mode: Full cursor control and ESC commands  
- String Mode: Fast line writing (ESC Q A/B)
- Scroll Mode: Continuous scrolling (ESC Q D/C)
- Smart transitions: Automatic mode management
"""

import time
import logging
import serial
from cd5220 import CD5220, CD5220DisplayError, DisplayMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s [TEST] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('CD5220_Test')

SERIAL_PORT = '/dev/tty.usbserial-A5XK3RJT'
BAUDRATE = 9600

def test_smart_mode_management(display: CD5220):
    """Test the smart mode management system."""
    logger.info("=== SMART MODE MANAGEMENT TESTS ===")
    
    # Test 1: String mode to cursor control (should auto-clear)
    logger.info("Test 1: String mode → Cursor control (auto-clear)")
    display.write_upper_line_string("STRING MODE TEXT")
    logger.info(f"Current mode: {display.current_mode.value}")
    
    # This should trigger auto-clear and mode transition
    display.cursor_on()
    display.set_cursor_position(1, 2)
    display.write_at_cursor("CURSOR WORKS!")
    time.sleep(2)
    display.cursor_off()
    
    # Test 2: String mode to brightness control (should auto-clear)
    logger.info("Test 2: String mode → Brightness control (auto-clear)")
    display.write_both_lines_string("BRIGHTNESS TEST", "STRING MODE")
    logger.info(f"Current mode: {display.current_mode.value}")
    
    # This should trigger auto-clear and mode transition
    display.set_brightness(4)
    display.write_positioned("BRIGHT & CLEAR!", 1, 1)
    display.write_positioned("NORMAL MODE", 1, 2)
    time.sleep(2)
    
    # Test 3: Manual mode control
    logger.info("Test 3: Manual mode transitions")
    display.write_upper_line_string("MANUAL CONTROL")
    logger.info(f"Before clear: {display.current_mode.value}")
    display.clear_display()
    logger.info(f"After clear: {display.current_mode.value}")
    
    logger.info("Smart mode management tests completed")

def test_normal_mode_features(display: CD5220):
    """Test all normal mode functionality."""
    logger.info("=== NORMAL MODE TESTS ===")
    
    display.clear_display()
    logger.info(f"Starting in {display.current_mode.value} mode")
    
    # Test brightness control
    logger.info("Testing brightness control")
    for level in range(1, 5):
        display.set_brightness(level)
        display.write_positioned(f"BRIGHTNESS: {level}/4", 1, 1)
        display.write_positioned("NORMAL MODE", 1, 2)
        time.sleep(1.5)
    
    # Test cursor functionality  
    logger.info("Testing cursor control")
    display.clear_display()
    display.write_positioned("CURSOR DEMO", 1, 1)
    display.cursor_on()
    
    # Move cursor through positions
    positions = [(1, 2), (5, 2), (10, 2), (15, 2), (20, 2)]
    for col, row in positions:
        display.set_cursor_position(col, row)
        time.sleep(0.5)
    
    # Test writing at cursor
    display.set_cursor_position(1, 2)
    display.write_at_cursor("Hello ")
    time.sleep(0.5)
    display.write_at_cursor("World!")
    time.sleep(1)
    display.cursor_off()
    
    # Test display modes
    logger.info("Testing display modes")
    display.clear_display()
    
    display.set_overwrite_mode()
    display.write_positioned("OVERWRITE MODE", 1, 1)
    display.write_positioned("ACTIVE", 1, 2)
    time.sleep(2)
    
    display.set_vertical_scroll_mode()
    display.write_positioned("VERTICAL SCROLL", 1, 1)
    display.write_positioned("MODE ACTIVE", 1, 2)
    time.sleep(2)
    
    display.set_horizontal_scroll_mode()
    display.write_positioned("HORIZONTAL MODE", 1, 1)
    display.write_positioned("ACTIVE", 1, 2)
    time.sleep(2)
    
    logger.info("Normal mode tests completed")

def test_string_mode_features(display: CD5220):
    """Test string mode functionality."""
    logger.info("=== STRING MODE TESTS ===")
    
    # Test basic string writing
    logger.info("Testing string mode line writing")
    display.write_upper_line_string("STRING MODE DEMO")
    display.write_lower_line_string("FAST LINE WRITING")
    logger.info(f"Current mode: {display.current_mode.value}")
    time.sleep(2)
    
    # Test both lines together
    display.write_both_lines_string("BOTH LINES", "UPDATED TOGETHER")
    time.sleep(2)
    
    # Test text handling
    display.write_upper_line_string("THIS IS A VERY LONG LINE THAT EXCEEDS TWENTY CHARACTERS")
    display.write_lower_line_string("TRUNCATED TO 20")
    time.sleep(2)
    
    # Test automatic padding
    display.write_upper_line_string("SHORT")
    display.write_lower_line_string("PADDED")
    time.sleep(2)
    
    logger.info("String mode tests completed")

def test_scroll_mode_features(display: CD5220):
    """Test scroll mode functionality."""
    logger.info("=== SCROLL MODE TESTS ===")
    
    # Test upper line scrolling
    logger.info("Testing upper line scroll")
    display.clear_display()
    display.write_positioned("SCROLL DEMO", 1, 2)  # Static text on line 2
    display.scroll_upper_line("CONTINUOUS SCROLLING TEXT ON UPPER LINE - THIS WILL SCROLL UNTIL STOPPED")
    logger.info(f"Current mode: {display.current_mode.value}")
    time.sleep(8)
    
    # Test lower line scrolling (stops upper scroll)
    logger.info("Testing lower line scroll")
    display.scroll_lower_line("LOWER LINE SCROLLING - NOTICE HOW THIS STOPS THE UPPER SCROLL AND STARTS LOWER")
    time.sleep(8)
    
    # Clear to stop scrolling
    logger.info("Stopping scroll with clear")
    display.clear_display()
    logger.info(f"Mode after clear: {display.current_mode.value}")
    
    logger.info("Scroll mode tests completed")

def test_mode_transition_scenarios(display: CD5220):
    """Test various mode transition scenarios."""
    logger.info("=== MODE TRANSITION SCENARIOS ===")
    
    # Scenario 1: String → Normal via cursor
    logger.info("Scenario 1: String mode → Cursor control")
    display.write_upper_line_string("STRING TO CURSOR")
    display.cursor_on()
    display.set_cursor_position(10, 2)
    display.write_at_cursor("SUCCESS!")
    display.cursor_off()
    time.sleep(2)
    
    # Scenario 2: String → Normal via brightness
    logger.info("Scenario 2: String mode → Brightness control")
    display.write_both_lines_string("STRING TO BRIGHT", "MODE TRANSITION")
    display.set_brightness(1)
    display.write_positioned("DIM", 1, 2)
    time.sleep(1)
    display.set_brightness(4)
    display.write_positioned("BRIGHT", 1, 2)
    time.sleep(2)
    
    # Scenario 3: Scroll → Normal via cursor
    logger.info("Scenario 3: Scroll mode → Cursor control")
    display.scroll_upper_line("SCROLLING TEXT BEFORE CURSOR")
    time.sleep(3)
    display.cursor_on()
    display.set_cursor_position(1, 2)
    display.write_at_cursor("CURSOR ACTIVE")
    display.cursor_off()
    time.sleep(2)
    
    # Scenario 4: Mixed operations
    logger.info("Scenario 4: Mixed mode operations")
    display.write_upper_line_string("MIXED OPERATIONS")
    display.set_brightness(2)  # Auto-clears
    display.write_positioned("BRIGHTNESS: 2", 1, 2)
    time.sleep(1)
    
    display.write_lower_line_string("STRING AGAIN")  # Enters string mode
    time.sleep(1)
    
    display.cursor_on()  # Auto-clears back to normal
    display.set_cursor_position(20, 2)
    display.cursor_off()
    time.sleep(2)
    
    logger.info("Mode transition scenarios completed")

def test_configuration_options(display: CD5220):
    """Test different configuration options."""
    logger.info("=== CONFIGURATION OPTIONS TEST ===")
    
    # Test with auto-clear disabled
    logger.info("Testing with auto-clear disabled")
    display.auto_clear_mode_transitions = False
    display.warn_on_mode_transitions = True
    
    display.write_upper_line_string("AUTO-CLEAR OFF")
    
    try:
        # This should fail without auto-clear
        display.cursor_on()
        logger.error("ERROR: Should have failed!")
    except CD5220DisplayError as e:
        logger.info(f"Expected error caught: {e}")
    
    # Manual clear should work
    display.clear_display()
    display.cursor_on()
    display.set_cursor_position(1, 2)
    display.write_at_cursor("MANUAL CLEAR OK")
    display.cursor_off()
    time.sleep(2)
    
    # Re-enable auto-clear
    display.auto_clear_mode_transitions = True
    logger.info("Re-enabled auto-clear")
    
    logger.info("Configuration options test completed")

def test_convenience_features(display: CD5220):
    """Test convenience methods."""
    logger.info("=== CONVENIENCE FEATURE TESTS ===")
    
    # Test display_message
    logger.info("Testing display_message convenience method")
    display.display_message("This is a long message that will wrap automatically", duration=2, mode="string")
    
    display.display_message("SHORTER MESSAGE", duration=2, mode="normal")
    
    # Test rapid updates
    logger.info("Testing rapid string updates")
    for i in range(5):
        display.write_both_lines_string(f"COUNTER: {i+1}", f"RAPID UPDATE #{i+1}")
        time.sleep(0.5)
    
    logger.info("Convenience feature tests completed")

def run_comprehensive_demo(display: CD5220):
    """Run a comprehensive demo showing all capabilities."""
    logger.info("=== COMPREHENSIVE DEMO ===")
    
    # Welcome message
    display.display_message("CD5220 SMART MODE DEMO - STARTING ALL TESTS", duration=3, mode="string")
    
    # Run all test suites
    test_smart_mode_management(display)
    time.sleep(1)
    
    test_normal_mode_features(display)
    time.sleep(1)
    
    test_string_mode_features(display)
    time.sleep(1)
    
    test_scroll_mode_features(display)
    time.sleep(1)
    
    test_mode_transition_scenarios(display)
    time.sleep(1)
    
    test_configuration_options(display)
    time.sleep(1)
    
    test_convenience_features(display)
    
    # Completion message
    display.clear_display()
    display.set_brightness(4)
    display.write_positioned("ALL TESTS", 1, 1)
    display.write_positioned("COMPLETED!", 1, 2)
    time.sleep(2)
    
    display.write_both_lines_string("SMART MODE DEMO", "FINISHED!")
    
    logger.info("=== COMPREHENSIVE DEMO COMPLETED ===")

def main():
    """Main test execution."""
    logger.info("CD5220 Smart Mode Management Test Suite")
    logger.info(f"Port: {SERIAL_PORT} | Baud: {BAUDRATE}")
    
    try:
        # Initialize with smart mode management enabled
        with CD5220(
            SERIAL_PORT, 
            BAUDRATE, 
            debug=True,
            auto_clear_mode_transitions=True,
            warn_on_mode_transitions=True
        ) as display:
            logger.info("Display initialized with smart mode management")
            logger.info(f"Starting in {display.current_mode.value} mode")
            
            run_comprehensive_demo(display)
            
            logger.info("All tests completed successfully!")
            
    except CD5220DisplayError as e:
        logger.error(f"Display error: {e}")
    except serial.SerialException as e:
        logger.error(f"Serial error: {e}")
    except Exception as e:
        logger.exception("Unexpected error occurred:")

if __name__ == '__main__':
    main()
