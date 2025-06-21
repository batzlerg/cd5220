#!/usr/bin/env python3
"""
CD5220 VFD Display Comprehensive Demo with Two Scrolling Paradigms

Demonstrates all documented modes and scrolling paradigms:
- Normal Mode: Full cursor control and ESC commands  
- String Mode: Fast line writing (ESC Q A/B)
- Continuous Scrolling (Marquee): Automatic movement at ~1Hz (ESC Q D - upper line only)
- Viewport Scrolling (Window-constrained): Overflow within defined boundaries (ESC W + ESC DC3)
- Smart transitions: Automatic mode management

Hardware Requirements:
- CD5220 VFD display (2x20 characters)
- RS232 connection at 9600 baud
- Display configured for PTC mode (DIP switches)

Key Discovery:
Two fundamentally different scrolling paradigms exist:
1. Continuous Marquee: Time-based automatic movement
2. Viewport Overflow: Event-triggered scrolling within window boundaries
"""

import time
import logging
import serial
import argparse
from cd5220 import CD5220, CD5220DisplayError, DisplayMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s [DEMO] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('CD5220_Demo')

class CD5220DemoFixture:
    """Demo fixture providing proper isolation between demo segments."""
    
    def __init__(self, display: CD5220, delay_multiplier: float = 1.0):
        self.display = display
        self.delay_multiplier = delay_multiplier
        
        # Hardware-aware timing constants
        self.BRIGHTNESS_PAUSE = 2.0 * delay_multiplier
        self.MODE_TRANSITION_DELAY = 0.5 * delay_multiplier
        self.VISUAL_CONFIRMATION_TIME = 2.5 * delay_multiplier
        self.SCROLL_OBSERVATION_TIME = 8.0 * delay_multiplier
        self.VIEWPORT_DEMO_TIME = 6.0 * delay_multiplier
        self.STEP_PAUSE = 1.0 * delay_multiplier
        
    def setup_demo(self, title: str, subtitle: str = "STARTING...") -> None:
        """Reset to known state and show demo title."""
        self.display.restore_defaults()
        title_truncated = title[:16] if len(title) > 16 else title
        self.display.write_both_lines_string(f"DEMO: {title_truncated}", subtitle)
        time.sleep(self.VISUAL_CONFIRMATION_TIME)
        
    def teardown_demo(self) -> None:
        """Clean up after demo."""
        self.display.restore_defaults()
        time.sleep(self.MODE_TRANSITION_DELAY)
        
    def show_banner(self, upper: str, lower: str = "", duration: float = None) -> None:
        """Show a banner with operator cues."""
        if duration is None:
            duration = self.VISUAL_CONFIRMATION_TIME
        self.display.write_both_lines_string(upper, lower)
        time.sleep(duration)
        
    def pause_for_observation(self, description: str, duration: float = None) -> None:
        """Pause with logging for operator observation."""
        if duration is None:
            duration = self.VISUAL_CONFIRMATION_TIME
        logger.info(f"Observe: {description} (pausing {duration:.1f}s)")
        time.sleep(duration)

def run_isolated_demo(display: CD5220, demo_func, title: str, fixture: CD5220DemoFixture):
    """Run a single demo with proper isolation."""
    logger.info(f"Starting demo: {title}")
    fixture.setup_demo(title)
    try:
        demo_func(display, fixture)
    finally:
        fixture.teardown_demo()
    logger.info(f"Completed demo: {title}")

def demo_smart_mode_management(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate the smart mode management system with clear visual flow."""
    
    # Test 1: Demonstrate string mode persistence
    fixture.show_banner("STEP 1: STRING MODE", "SHOWING PERSISTENCE")
    display.write_upper_line_string("THIS IS STRING MODE")
    display.write_lower_line_string("TEXT STAYS VISIBLE")
    fixture.pause_for_observation("String mode text visible", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Show mode status
    fixture.show_banner("STRING MODE ACTIVE", f"MODE: {display.current_mode.value.upper()}")
    fixture.pause_for_observation("Mode indicator", fixture.STEP_PAUSE)
    
    # Test 2: Demonstrate auto-clear transition
    fixture.show_banner("STEP 2: AUTO-CLEAR", "TRIGGERING TRANSITION")
    
    # Put content back for the transition demo
    display.write_upper_line_string("ABOUT TO AUTO-CLEAR")
    display.write_lower_line_string("WATCH TEXT VANISH")
    fixture.pause_for_observation("Text before auto-clear", fixture.VISUAL_CONFIRMATION_TIME)
    
    # This triggers auto-clear - user will see text disappear
    logger.info("Triggering auto-clear by enabling cursor...")
    display.cursor_on()
    display.set_cursor_position(1, 1)
    display.write_at_cursor("AUTO-CLEAR WORKED!")
    display.set_cursor_position(1, 2)
    display.write_at_cursor("NOW IN NORMAL MODE")
    display.cursor_off()
    fixture.pause_for_observation("After auto-clear transition", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test 3: Manual mode control demonstration
    fixture.show_banner("STEP 3: MANUAL CTRL", "EXPLICIT CLEARING")
    display.write_upper_line_string("MANUAL CONTROL DEMO")
    display.write_lower_line_string("WILL CLEAR MANUALLY")
    fixture.pause_for_observation("Text before manual clear", fixture.VISUAL_CONFIRMATION_TIME)
    
    logger.info(f"Before manual clear: {display.current_mode.value}")
    display.clear_display()
    logger.info(f"After manual clear: {display.current_mode.value}")
    
    display.write_positioned("CLEARED BY USER", 1, 1)
    display.write_positioned("EXPLICIT COMMAND", 1, 2)
    fixture.pause_for_observation("After manual clear", fixture.VISUAL_CONFIRMATION_TIME)

def demo_normal_mode_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate all normal mode functionality with proper content for brightness observation."""
    
    # Test brightness control with content visible - start from level 1, rewrite both lines
    fixture.show_banner("BRIGHTNESS DEMO", "OBSERVE CHANGES")
    
    # Start with brightness level 1 for better demonstration
    display.set_brightness(1)
    display.write_both_lines_string("BRIGHTNESS TEST", "LEVEL: 1/4 (MIN)")
    fixture.pause_for_observation("Brightness level 1", fixture.BRIGHTNESS_PAUSE)
    
    # Progress through brightness levels, rewriting both lines completely
    for level in range(2, 5):  # Count up from 2 to 4
        display.set_brightness(level)
        level_text = f"LEVEL: {level}/4" + (" (MAX)" if level == 4 else "")
        display.write_both_lines_string("BRIGHTNESS TEST", level_text)
        fixture.pause_for_observation(f"Brightness level {level}", fixture.BRIGHTNESS_PAUSE)
    
    fixture.pause_for_observation("Brightness demonstration complete", fixture.STEP_PAUSE)
    
    # Test cursor functionality  
    fixture.show_banner("CURSOR DEMO", "POSITIONING")
    display.clear_display()
    display.write_positioned("CURSOR DEMO", 1, 1)
    display.cursor_on()
    
    # Move cursor through positions with visible feedback
    positions = [(1, 2), (5, 2), (10, 2), (15, 2), (20, 2)]
    for i, (col, row) in enumerate(positions):
        display.set_cursor_position(col, row)
        display.write_at_cursor(str(i+1))
        time.sleep(0.5 * fixture.delay_multiplier)
    
    fixture.pause_for_observation("Cursor positioning complete", fixture.STEP_PAUSE)
    
    # Test writing at cursor
    display.set_cursor_position(1, 2)
    display.write_at_cursor("HELLO WORLD!")
    display.cursor_off()
    fixture.pause_for_observation("Cursor writing demo", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test display modes with actual scrolling behavior
    fixture.show_banner("DISPLAY MODES", "TESTING")
    
    # Ensure we start in overwrite mode
    display.set_overwrite_mode()
    display.write_positioned("OVERWRITE MODE", 1, 1)
    display.write_positioned("ACTIVE NOW", 1, 2)
    fixture.pause_for_observation("Overwrite mode", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Demonstrate vertical scroll mode with actual scrolling
    display.set_vertical_scroll_mode()
    display.clear_display()
    display.write_positioned("VERTICAL SCROLL", 1, 1)
    display.write_positioned("WRITING TO OVERFLOW", 1, 2)
    fixture.pause_for_observation("Vertical scroll mode setup", fixture.STEP_PAUSE)
    
    # Force vertical scrolling by writing multiple lines that overflow
    display.set_cursor_position(1, 2)
    overflow_text = "LINE3 CONTENT FORCES SCROLL UP TO DEMONSTRATE VERTICAL SCROLL MODE BEHAVIOR"
    for char in overflow_text:
        display.write_at_cursor(char)
        time.sleep(0.05 * fixture.delay_multiplier)  # Slow enough to see scrolling
    fixture.pause_for_observation("Vertical scrolling in action", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Explicitly restore overwrite mode before exit
    display.set_overwrite_mode()
    fixture.pause_for_observation("Overwrite mode restored", fixture.STEP_PAUSE)

def demo_string_mode_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate string mode functionality."""
    
    # Test basic string writing
    fixture.show_banner("STRING MODE", "FAST WRITING")
    display.write_upper_line_string("STRING MODE DEMO")
    display.write_lower_line_string("FAST LINE WRITING")
    logger.info(f"Current mode: {display.current_mode.value}")
    fixture.pause_for_observation("String mode writing", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test both lines together
    fixture.show_banner("BOTH LINES", "TOGETHER")
    display.write_both_lines_string("BOTH LINES AT ONCE", "UPDATED TOGETHER")
    fixture.pause_for_observation("Both lines updated", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test text handling (truncation)
    fixture.show_banner("TEXT HANDLING", "AUTO TRUNCATE")
    display.write_upper_line_string("THIS IS A VERY LONG LINE THAT EXCEEDS TWENTY CHARACTERS")
    display.write_lower_line_string("TRUNCATED TO 20")
    fixture.pause_for_observation("Long text truncation", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test automatic padding
    fixture.show_banner("AUTO PADDING", "SHORT TEXT")
    display.write_upper_line_string("SHORT")
    display.write_lower_line_string("PADDED")
    fixture.pause_for_observation("Text padding", fixture.VISUAL_CONFIRMATION_TIME)

def demo_continuous_scrolling_marquee(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate continuous marquee scrolling - the classic scrolling paradigm."""
    
    # Test continuous marquee scrolling with clear setup
    fixture.show_banner("MARQUEE SCROLLING", "CONTINUOUS MOVEMENT")
    display.clear_display()
    display.write_positioned("STATIC ON LINE 2", 1, 2)  # Static text on line 2
    fixture.pause_for_observation("Setup for marquee scroll", fixture.STEP_PAUSE)
    
    scroll_text = "CONTINUOUS MARQUEE SCROLLING AT 1HZ - AUTOMATIC MOVEMENT UNTIL STOPPED"
    display.scroll_marquee(scroll_text)
    logger.info(f"Current mode: {display.current_mode.value}")
    
    # Observation time for marquee scrolling
    observation_time = fixture.SCROLL_OBSERVATION_TIME
    logger.info(f"Observing marquee scroll for {observation_time:.1f} seconds")
    time.sleep(observation_time)
    
    # Demonstrate hardware limitation - no lower line marquee support
    logger.info("CD5220 hardware only supports upper line marquee scrolling")
    fixture.show_banner("HARDWARE LIMIT", "UPPER MARQUEE ONLY", duration=3.0)
    
    # Show alternative: string mode for lower line updates
    fixture.show_banner("ALTERNATIVE", "STRING MODE LOWER")
    display.cancel_current_line()  # Exit scroll mode cleanly
    
    # Demonstrate string mode for lower line (ESC Q B)
    display.write_positioned("STATIC UPPER LINE", 1, 1)
    for i in range(5):
        display.write_lower_line_string(f"LOWER UPDATE #{i+1}")
        time.sleep(0.8 * fixture.delay_multiplier)
    
    fixture.pause_for_observation("String mode lower line updates", fixture.VISUAL_CONFIRMATION_TIME)

def demo_viewport_overflow_scrolling(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate window-constrained viewport overflow scrolling - the newly discovered paradigm."""
    
    # Introduction to viewport concept
    fixture.show_banner("VIEWPORT SCROLLING", "WINDOW CONSTRAINED")
    fixture.show_banner("ESC W + ESC DC3", "OVERFLOW HANDLING", duration=3.0)
    
    # Test 1: Basic window setup and overflow
    fixture.show_banner("TEST 1: BASIC", "WINDOW OVERFLOW")
    display.clear_display()
    
    # Set up static context FIRST, before entering viewport mode
    display.write_positioned("1234", 1, 1)      # Before window
    display.write_positioned("67890", 16, 1)    # After window
    display.write_positioned("WINDOW: COLS 5-15", 1, 2)
    
    # NOW set window and enter viewport mode
    display.set_window(1, 5, 15)
    display.enter_viewport_mode()
    
    # Demonstrate overflow scrolling character by character
    test_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(1, len(test_text) + 1):
        display.write_viewport(1, test_text[:i])
        time.sleep(0.3 * fixture.delay_multiplier)
        if i > 20:  # Stop after sufficient demonstration
            break
    
    fixture.pause_for_observation("Viewport overflow scrolling", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test 2: Dual windows on both lines
    fixture.show_banner("TEST 2: DUAL", "BOTH LINES")
    display.clear_display()
    
    # Set up static markers FIRST
    display.write_positioned("12", 1, 1)        # Before line 1 window
    display.write_positioned("34567", 1, 2)     # Before line 2 window
    display.write_positioned("90", 19, 2)       # After line 2 window
    
    # NOW set different windows on both lines
    display.set_window(1, 3, 12)   # Line 1: columns 3-12 (10 chars)
    display.set_window(2, 8, 18)   # Line 2: columns 8-18 (11 chars)
    display.enter_viewport_mode()
    
    # Demonstrate both viewports
    display.write_viewport(1, "VIEWPORT ONE TEXT OVERFLOW")
    time.sleep(2 * fixture.delay_multiplier)
    
    display.write_viewport(2, "VIEWPORT TWO DIFFERENT WINDOW")
    fixture.pause_for_observation("Dual viewport demonstration", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test 3: Window management
    fixture.show_banner("TEST 3: WINDOW", "MANAGEMENT")
    display.clear_display()
    
    # Show window info
    windows = display.active_windows
    window_info = f"WIN: {len(windows)} ACTIVE"
    display.write_positioned(window_info, 1, 1)
    display.write_positioned(f"L1:{windows.get(1,'NONE')}", 1, 2)
    fixture.pause_for_observation("Window status", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Clear windows
    display.clear_all_windows()
    display.write_positioned("ALL WINDOWS", 1, 1)
    display.write_positioned("CLEARED", 1, 2)
    fixture.pause_for_observation("Windows cleared", fixture.VISUAL_CONFIRMATION_TIME)

def demo_scrolling_paradigm_comparison(display: CD5220, fixture: CD5220DemoFixture):
    """Compare the two scrolling paradigms side by side."""
    
    fixture.show_banner("PARADIGM COMPARE", "TWO SCROLL TYPES")
    
    # Paradigm 1: Continuous Marquee
    fixture.show_banner("PARADIGM 1", "CONTINUOUS MARQUEE")
    display.clear_display()
    display.write_positioned("TIME-BASED AUTO", 1, 2)
    
    display.scroll_marquee("MARQUEE: AUTOMATIC MOVEMENT AT 1HZ REFRESH RATE")
    time.sleep(6 * fixture.delay_multiplier)
    
    # Paradigm 2: Viewport Overflow  
    fixture.show_banner("PARADIGM 2", "VIEWPORT OVERFLOW")
    display.clear_display()
    
    # Set up static context FIRST
    display.write_positioned("12345", 1, 1)     # Before window
    display.write_positioned("78901", 17, 1)    # After window
    display.write_positioned("EVENT-TRIGGERED", 1, 2)
    
    # NOW enter viewport mode
    display.set_window(1, 6, 16)  # 11-character window
    display.enter_viewport_mode()
    
    # Show overflow behavior
    overflow_demo = "VIEWPORT OVERFLOW WITHIN WINDOW BOUNDARIES"
    for i in range(5, len(overflow_demo) + 1, 3):
        display.write_viewport(1, overflow_demo[:i])
        time.sleep(0.5 * fixture.delay_multiplier)
    
    fixture.pause_for_observation("Paradigm comparison complete", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Summary
    fixture.show_banner("TWO PARADIGMS", "DIFFERENT USES")
    fixture.show_banner("MARQUEE: ANNOUNCE", "VIEWPORT: CONSTRAIN", duration=4.0)

def demo_configuration_options(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate different configuration options."""
    
    fixture.show_banner("CONFIG OPTIONS", "AUTO-CLEAR OFF")
    
    # Save original settings
    original_auto_clear = display.auto_clear_mode_transitions
    original_warn = display.warn_on_mode_transitions
    
    try:
        # Test with auto-clear disabled
        display.auto_clear_mode_transitions = False
        display.warn_on_mode_transitions = True
        
        display.write_upper_line_string("AUTO-CLEAR OFF")
        display.write_lower_line_string("MODE PROTECTION ON")
        fixture.pause_for_observation("Auto-clear disabled", fixture.VISUAL_CONFIRMATION_TIME)
        
        try:
            # This should fail without auto-clear
            display.cursor_on()
            logger.error("ERROR: Should have failed!")
        except CD5220DisplayError as e:
            logger.info(f"Expected error caught: {e}")
            fixture.show_banner("ERROR CAUGHT", "AS EXPECTED")
            fixture.pause_for_observation("Error protection working", fixture.VISUAL_CONFIRMATION_TIME)
        
        # Manual clear should work
        display.clear_display()
        display.cursor_on()
        display.set_cursor_position(1, 1)
        display.write_at_cursor("MANUAL CLEAR OK")
        display.set_cursor_position(1, 2)
        display.write_at_cursor("PROTECTION WORKS")
        display.cursor_off()
        fixture.pause_for_observation("Manual clear successful", fixture.VISUAL_CONFIRMATION_TIME)
        
    finally:
        # Restore original settings
        display.auto_clear_mode_transitions = original_auto_clear
        display.warn_on_mode_transitions = original_warn
        logger.info("Restored original configuration")

def demo_convenience_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate convenience methods including viewport demos."""
    
    # Test display_message
    fixture.show_banner("CONVENIENCE", "METHODS")
    display.display_message("This is a long message that will wrap automatically across lines", 
                          duration=fixture.VISUAL_CONFIRMATION_TIME, mode="string")
    
    display.display_message("SHORTER MESSAGE IN NORMAL MODE", 
                          duration=fixture.VISUAL_CONFIRMATION_TIME, mode="normal")
    
    # Test viewport demo convenience method
    fixture.show_banner("VIEWPORT DEMO", "CONVENIENCE METHOD")
    display.clear_display()
    
    # Set up static context FIRST
    display.write_positioned("DEMO: COLS 7-17", 1, 2)
    
    # Use convenience method (which handles viewport setup internally)
    display.create_viewport_demo(1, 7, 17, "CONVENIENCE METHOD FOR VIEWPORT DEMONSTRATION", 0.3)
    
    fixture.pause_for_observation("Viewport convenience demo", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test rapid updates (staying in string mode)
    fixture.show_banner("RAPID UPDATES", "STRING MODE")
    for i in range(5):
        display.write_both_lines_string(f"COUNTER: {i+1}", f"RAPID UPDATE #{i+1}")
        time.sleep(0.5 * fixture.delay_multiplier)
    
    fixture.pause_for_observation("Rapid update sequence", fixture.STEP_PAUSE)

def run_comprehensive_demo(display: CD5220, config):
    """Run a comprehensive demo showing all capabilities."""
    logger.info("=== CD5220 COMPREHENSIVE DEMO ===")
    
    fixture = CD5220DemoFixture(display, config.delay_multiplier)
    
    # Welcome message
    display.display_message("CD5220 TWO SCROLLING PARADIGMS DEMO - STARTING", 
                          duration=3 * config.delay_multiplier, mode="string")
    
    # Demo suites based on CLI selection
    demo_suites = {
        'modes': [
            (demo_normal_mode_features, "NORMAL MODE"),
            (demo_string_mode_features, "STRING MODE")
        ],
        'scrolling': [
            (demo_continuous_scrolling_marquee, "MARQUEE SCROLL"),
            (demo_viewport_overflow_scrolling, "VIEWPORT SCROLL"),
            (demo_scrolling_paradigm_comparison, "PARADIGM COMPARE")
        ],
        'smart': [
            (demo_smart_mode_management, "SMART MGMT")
        ],
        'config': [
            (demo_configuration_options, "CONFIG OPT")
        ],
        'convenience': [
            (demo_convenience_features, "CONVENIENCE")
        ]
    }
    
    if config.demo == 'all':
        selected_demos = []
        for suite in demo_suites.values():
            selected_demos.extend(suite)
    else:
        selected_demos = demo_suites.get(config.demo, demo_suites['modes'])
    
    # Run selected demos
    for demo_func, title in selected_demos:
        run_isolated_demo(display, demo_func, title, fixture)
        
        if not config.auto_advance:
            input("Press Enter to continue to next demo...")
        else:
            time.sleep(1.0 * config.delay_multiplier)
    
    # Completion message
    display.clear_display()
    display.set_brightness(4)
    display.write_positioned("ALL DEMOS", 1, 1)
    display.write_positioned("COMPLETED!", 1, 2)
    time.sleep(2 * config.delay_multiplier)
    
    display.write_both_lines_string("TWO PARADIGMS", "DEMONSTRATED!")
    time.sleep(2 * config.delay_multiplier)
    
    logger.info("=== COMPREHENSIVE DEMO COMPLETED ===")

def main():
    """Main demo execution with CLI configuration."""
    parser = argparse.ArgumentParser(description="CD5220 VFD Display Demo - Two Scrolling Paradigms")
    parser.add_argument('--port', default='/dev/tty.usbserial-A5XK3RJT', 
                       help='Serial port device')
    parser.add_argument('--baud', type=int, default=9600, 
                       help='Baud rate (default: 9600)')
    parser.add_argument('--fast', action='store_true', 
                       help='Reduce delays for experienced users')
    parser.add_argument('--demo', choices=['all', 'modes', 'scrolling', 'smart', 'config', 'convenience'], 
                       default='all', help='Run specific demo suite')
    parser.add_argument('--auto-advance', action='store_true',
                       help='Auto-advance between demos (no manual input)')
    parser.add_argument('--command-delay', type=float, default=0.05,
                       help='Base command delay in seconds')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose debug logging')
    
    args = parser.parse_args()
    
    # Configure timing
    args.delay_multiplier = 0.3 if args.fast else 1.0
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("CD5220 Two Scrolling Paradigms Demo Suite")
    logger.info(f"Port: {args.port} | Baud: {args.baud} | Demo: {args.demo}")
    logger.info(f"Fast mode: {args.fast} | Auto-advance: {args.auto_advance}")
    
    try:
        # Initialize with smart mode management enabled
        with CD5220(
            args.port, 
            args.baud, 
            debug=args.verbose,
            auto_clear_mode_transitions=True,
            warn_on_mode_transitions=True,
            command_delay=args.command_delay
        ) as display:
            logger.info("Display initialized with smart mode management")
            logger.info(f"Starting in {display.current_mode.value} mode")
            
            run_comprehensive_demo(display, args)
            
            logger.info("All demos completed successfully!")
            
    except CD5220DisplayError as e:
        logger.error(f"Display error: {e}")
    except serial.SerialException as e:
        logger.error(f"Serial error: {e}")
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.exception("Unexpected error occurred:")

if __name__ == '__main__':
    main()
