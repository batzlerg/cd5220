#!/usr/bin/env python3
"""
CD5220 VFD Display Test Script (Complete)

Exercises all library features with comprehensive debug logging.
"""

import serial
import time
import logging
from cd5220 import CD5220, CD5220DisplayError

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s [TEST] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('CD5220_Test')

SERIAL_PORT = '/dev/tty.usbserial-A5XK3RJT'
BAUDRATE = 9600

def run_brightness_test(display):
    """Brightness test with visual feedback"""
    logger.info("Starting brightness test")
    for level in range(1, 5):
        logger.debug(f"Setting brightness to level {level}")
        display.set_brightness(level)
        display.write_upper_line(f"BRIGHTNESS LEVEL")
        display.write_lower_line(f"SET TO: {level}/4")
        time.sleep(2.5)
    logger.info("Brightness test completed")

def run_cursor_test(display):
    """Cursor functionality test with logging"""
    logger.info("Starting cursor test")
    display.clear_display()
    display.write_upper_line("CURSOR TEST")
    
    # Enable cursor
    display.cursor_on()
    
    # Test cursor positioning
    positions = [(1, 2), (5, 2), (10, 2), (15, 2), (20, 2)]
    for col, row in positions:
        logger.debug(f"Moving cursor to ({col},{row})")
        display.set_cursor_position(col, row)
        time.sleep(0.5)
    
    # Test manual ASCII writing
    display.set_cursor_position(1, 2)
    display.write_at_cursor("Hello ")
    time.sleep(0.5)
    display.write_at_cursor("World!")
    time.sleep(1)
    
    display.cursor_off()
    logger.info("Cursor test completed")

def run_scroll_test(display):
    """Scrolling functionality test with extended duration"""
    logger.info("Starting scroll test with extended duration")
    display.clear_display()
    display.write_upper_line("SCROLL TEST")
    
    logger.debug("Testing upper line scroll")
    display.scroll_upper_line("SCROLLING TEXT ON UPPER LINE: " + "~"*50)
    time.sleep(10)  # Extended duration
    
    logger.debug("Testing lower line scroll")
    display.scroll_lower_line("SCROLLING TEXT ON LOWER LINE: " + "-"*50)
    time.sleep(10)  # Extended duration
    
    logger.info("Scroll test completed")

def run_mode_test(display):
    """Display mode test with logging"""
    logger.info("Starting mode test")
    
    display.set_overwrite_mode()
    display.write_both_lines("OVERWRITE MODE", "ACTIVE")
    time.sleep(2)
    
    display.set_vertical_scroll_mode()
    display.write_both_lines("VERTICAL SCROLL", "MODE ACTIVE")
    time.sleep(2)
    
    display.set_horizontal_scroll_mode()
    display.write_both_lines("HORIZONTAL SCROLL", "MODE ACTIVE")
    time.sleep(2)
    
    # Restore default mode
    display.set_overwrite_mode()
    logger.info("Mode test completed")

def run_comprehensive_test(display):
    """Run the built-in comprehensive test"""
    logger.info("Starting comprehensive test")
    display.test_display()
    logger.info("Comprehensive test completed")

def main():
    logger.info("CD5220 Comprehensive Test Sequence")
    logger.info(f"Port: {SERIAL_PORT} | Baud: {BAUDRATE}")
    
    try:
        # Initialize with debug enabled
        logger.debug("Creating display instance")
        display = CD5220(SERIAL_PORT, BAUDRATE, debug=True)
        
        with display:
            logger.info("Display initialized. Starting tests...")
            
            # Run test sequence
            run_brightness_test(display)
            time.sleep(1)
            
            run_cursor_test(display)
            time.sleep(1)
            
            run_scroll_test(display)
            time.sleep(1)
            
            run_mode_test(display)
            time.sleep(1)
            
            run_comprehensive_test(display)
            
            # Final message
            display.write_both_lines("ALL TESTS COMPLETE", "DISPLAY READY")
            logger.info("All tests completed successfully")
            time.sleep(2)
            
    except CD5220DisplayError as e:
        logger.error(f"Display error: {e}")
    except serial.SerialException as e:
        logger.error(f"Serial error: {e}")
    except Exception as e:
        logger.exception("Unexpected error:")

if __name__ == '__main__':
    main()
