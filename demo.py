#!/usr/bin/env python3
"""
CD5220 VFD Display Comprehensive Demo

Demonstrates all documented modes and features with proper test isolation:
- Normal Mode: Cursor control, brightness, positioning  
- String Mode: Fast line writing
- Continuous Scrolling: Automatic marquee movement (upper line only)
- Viewport Mode: Window-constrained display with smooth overflow handling
- Smart Mode Management: Automatic transitions and error handling
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
    """Demo fixture providing proper isolation and timing control."""
    
    def __init__(self, display: CD5220, delay_multiplier: float = 1.0):
        self.display = display
        self.delay_multiplier = delay_multiplier
        
        # Timing constants
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
        self.display.write_both_lines(f"DEMO: {title_truncated}", subtitle)
        time.sleep(self.VISUAL_CONFIRMATION_TIME)
        
    def teardown_demo(self) -> None:
        """Clean teardown after each demo."""
        self.display.restore_defaults()
        time.sleep(self.MODE_TRANSITION_DELAY)
        
    def show_banner(self, upper: str, lower: str = "", duration: float = None) -> None:
        """Show a banner message."""
        if duration is None:
            duration = self.VISUAL_CONFIRMATION_TIME
        self.display.write_both_lines(upper, lower)
        time.sleep(duration)
        
    def pause_for_observation(self, description: str, duration: float = None) -> None:
        """Pause with logging for operator observation."""
        if duration is None:
            duration = self.VISUAL_CONFIRMATION_TIME
        logger.info(f"Observe: {description} (pausing {duration:.1f}s)")
        time.sleep(duration)

def isolated_demo(title: str):
    """
    Decorator that wraps an individual demo function with:
    • CD5220DemoFixture creation
    • automatic setup / teardown
    • uniform logging
    """
    def decorator(fn):
        def wrapped(display: CD5220, delay_multiplier: float):
            fixture = CD5220DemoFixture(display, delay_multiplier)
            logger.info(f"Starting demo: {title}")
            fixture.setup_demo(title)
            try:
                fn(display, fixture)          # run user demo
            finally:
                fixture.teardown_demo()
            logger.info(f"Completed demo: {title}")
        return wrapped
    return decorator

@isolated_demo("NORMAL MODE")
def demo_normal_mode_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate normal mode functionality with proper state isolation."""
    
    # Test brightness control with content visible
    fixture.show_banner("BRIGHTNESS DEMO", "OBSERVE CHANGES")
    
    # Start with brightness level 1 for maximum contrast demonstration
    display.set_brightness(1)
    display.write_both_lines("BRIGHTNESS TEST", "LEVEL: 1/4 (MIN)")
    fixture.pause_for_observation("Brightness level 1", fixture.BRIGHTNESS_PAUSE)
    
    # Progress through brightness levels
    for level in range(2, 5):
        display.set_brightness(level)
        level_text = f"LEVEL: {level}/4" + (" (MAX)" if level == 4 else "")
        display.write_both_lines("BRIGHTNESS TEST", level_text)
        fixture.pause_for_observation(f"Brightness level {level}", fixture.BRIGHTNESS_PAUSE)
    
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
    
    display.cursor_off()
    fixture.pause_for_observation("Cursor positioning complete", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test positioned writing
    display.clear_display()
    display.write_positioned("NORMAL MODE", 1, 1)
    display.write_positioned("POSITIONED TEXT", 1, 2)
    fixture.pause_for_observation("Normal mode writing", fixture.VISUAL_CONFIRMATION_TIME)

@isolated_demo("STRING MODE")
def demo_string_mode_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate string mode functionality with proper isolation."""
    
    # Test basic string writing
    fixture.show_banner("STRING MODE", "FAST WRITING")
    display.write_upper_line("STRING MODE DEMO")
    display.write_lower_line("FAST LINE WRITING")
    logger.info(f"Current mode: {display.current_mode.value}")
    fixture.pause_for_observation("String mode writing", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test both lines together
    display.write_both_lines("BOTH LINES", "UPDATED TOGETHER")
    fixture.pause_for_observation("Both lines updated", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test text handling (intentional truncation demo)
    fixture.show_banner("TEXT HANDLING", "TRUNCATION TEST")
    display.write_upper_line("THIS IS A VERY LONG LINE THAT EXCEEDS TWENTY CHARACTERS")
    display.write_lower_line("TRUNCATED TO 20")
    fixture.pause_for_observation("Long text truncation", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test automatic padding
    display.write_both_lines("SHORT", "AUTO PADDED")
    fixture.pause_for_observation("Text padding", fixture.VISUAL_CONFIRMATION_TIME)

@isolated_demo("MARQUEE SCROLL")
def demo_continuous_scrolling(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate continuous marquee scrolling."""
    
    fixture.show_banner("MARQUEE SCROLLING", "CONTINUOUS MOVEMENT")
    display.clear_display()
    display.write_positioned("STATIC LINE 2", 1, 2)
    fixture.pause_for_observation("Setup for marquee", fixture.STEP_PAUSE)
    
    scroll_text = "CONTINUOUS MARQUEE SCROLLING AT 1HZ - AUTOMATIC MOVEMENT UNTIL STOPPED"
    display.scroll_marquee(scroll_text)
    logger.info(f"Current mode: {display.current_mode.value}")
    
    # Allow sufficient observation time
    time.sleep(fixture.SCROLL_OBSERVATION_TIME)
    
    # Clean exit from scroll mode
    display.cancel_current_line()
    fixture.show_banner("MARQUEE COMPLETE", "UPPER LINE ONLY")
    fixture.pause_for_observation("Hardware limitation noted", fixture.VISUAL_CONFIRMATION_TIME)

@isolated_demo("VIEWPORT MODE")
def demo_viewport_mode(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate window-constrained viewport mode with smooth incremental building."""
    
    # Test 1: Smooth incremental character building
    fixture.show_banner("VIEWPORT MODE", "WINDOW CONSTRAINED")
    display.clear_display()
    
    # Set up static context FIRST with consistent 1-based indexing
    display.write_positioned("****", 1, 1)      # Positions 1-4
    display.write_positioned("****", 17, 1)     # Positions 17-20
    display.write_positioned("WINDOW: COLS 5-16", 1, 2)  # Updated label
    
    # NOW set window with 1-based indexing and enter viewport mode
    display.set_window(1, 5, 16)  # Window columns 5-16 (12 characters)
    display.enter_viewport_mode()
    
    # Demonstrate smooth incremental character building
    test_text = "INCREMENTAL_DEMO_TEXT"
    display.write_viewport(1, test_text, char_delay=0.3 * fixture.delay_multiplier)
    
    fixture.pause_for_observation("Smooth incremental building", fixture.VIEWPORT_DEMO_TIME)
    
    # Test 2: Fast viewport writing (original behavior)
    fixture.show_banner("FAST VIEWPORT", "INSTANT WRITING")
    display.clear_display()
    
    # Static markers
    display.write_positioned("ID:[", 1, 1)
    display.write_positioned("]", 16, 1)
    display.write_positioned("FAST MODE", 1, 2)
    
    # Different window for variety
    display.set_window(1, 5, 15)
    display.enter_viewport_mode()
    
    # Fast writing (no char_delay)
    display.write_viewport(1, "INSTANT_OVERFLOW_TEXT")
    fixture.pause_for_observation("Fast viewport writing", fixture.VISUAL_CONFIRMATION_TIME)

@isolated_demo("SMART MGMT")
def demo_smart_mode_management(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate smart mode management with clear transitions."""
    
    # Test auto-clear behavior
    fixture.show_banner("SMART MGMT", "AUTO TRANSITIONS")
    
    # Enter string mode
    display.write_both_lines("IN STRING MODE", "AUTO-CLEAR PENDING")
    fixture.pause_for_observation("String mode active", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Trigger auto-clear with normal mode operation
    logger.info("Triggering auto-clear...")
    display.set_brightness(3)  # This requires normal mode
    display.write_positioned("AUTO-CLEAR WORKED", 1, 1)
    display.write_positioned("NOW NORMAL MODE", 1, 2)
    fixture.pause_for_observation("Auto-clear completed", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test manual mode control
    fixture.show_banner("MANUAL CONTROL", "EXPLICIT CLEARING")
    display.write_upper_line("MANUAL DEMO")
    display.write_lower_line("WILL CLEAR MANUALLY")
    fixture.pause_for_observation("Before manual clear", fixture.STEP_PAUSE)
    
    display.clear_display()
    display.write_positioned("MANUAL CLEAR OK", 1, 1)
    display.write_positioned("USER CONTROLLED", 1, 2)
    fixture.pause_for_observation("Manual clear completed", fixture.VISUAL_CONFIRMATION_TIME)

@isolated_demo("CONFIG OPT")
def demo_configuration_options(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate configuration options including error protection."""
    
    fixture.show_banner("CONFIG OPTIONS", "ERROR PROTECTION")
    
    # Save original settings
    original_auto_clear = display.auto_clear_mode_transitions
    original_warn = display.warn_on_mode_transitions
    
    try:
        # Test with auto-clear disabled
        display.auto_clear_mode_transitions = False
        display.warn_on_mode_transitions = True
        
        display.write_both_lines("AUTO-CLEAR OFF", "PROTECTION ACTIVE")
        fixture.pause_for_observation("Protection enabled", fixture.VISUAL_CONFIRMATION_TIME)
        
        # This should fail
        try:
            display.cursor_on()
            logger.error("ERROR: Protection failed!")
        except CD5220DisplayError as e:
            logger.info(f"Expected error: {e}")
            fixture.show_banner("ERROR CAUGHT", "PROTECTION WORKS")
            fixture.pause_for_observation("Error protection working", fixture.VISUAL_CONFIRMATION_TIME)
        
        # Manual clear should work
        display.clear_display()
        display.write_positioned("MANUAL CLEAR OK", 1, 1)
        display.write_positioned("PROTECTION WORKS", 1, 2)
        fixture.pause_for_observation("Manual override", fixture.VISUAL_CONFIRMATION_TIME)
        
    finally:
        # Restore original settings
        display.auto_clear_mode_transitions = original_auto_clear
        display.warn_on_mode_transitions = original_warn

@isolated_demo("CONVENIENCE")
def demo_convenience_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate convenience methods."""
    
    # Test display_message
    fixture.show_banner("CONVENIENCE", "METHODS")
    display.display_message("Auto-wrapped message across lines", 
                          duration=fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test viewport convenience with smooth building
    fixture.show_banner("SMOOTH VIEWPORT", "CONVENIENCE DEMO")
    display.clear_display()
    display.write_positioned("DEMO: COLS 6-16", 1, 2)
    
    # Manual viewport setup for demonstration
    display.set_window(1, 6, 16)
    display.enter_viewport_mode()
    display.write_viewport(1, "CONVENIENCE_DEMO_TEXT", char_delay=0.25 * fixture.delay_multiplier)
    fixture.pause_for_observation("Smooth convenience demo", fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test rapid updates
    fixture.show_banner("RAPID UPDATES", "STRING MODE")
    for i in range(5):
        display.write_both_lines(f"UPDATE: {i+1}", f"COUNTER: {i+1}")
        time.sleep(0.4 * fixture.delay_multiplier)
    
    fixture.pause_for_observation("Rapid updates complete", fixture.STEP_PAUSE)

def run_comprehensive_demo(display: CD5220, config):
    """Run comprehensive demo with balanced feature coverage."""
    logger.info("=== CD5220 COMPREHENSIVE DEMO ===")
    
    # Welcome message
    display.display_message("CD5220 COMPREHENSIVE DEMO - STARTING", 
                          duration=3 * config.delay_multiplier)
    
    # Demo suites with balanced coverage
    demo_suites = {
        'core': [
            demo_normal_mode_features,
            demo_string_mode_features,
            demo_smart_mode_management
        ],
        'scrolling': [
            demo_continuous_scrolling,
            demo_viewport_mode
        ],
        'config': [
            demo_configuration_options
        ],
        'convenience': [
            demo_convenience_features
        ]
    }
    
    if config.demo == 'all':
        selected_demos = []
        for suite in demo_suites.values():
            selected_demos.extend(suite)
    else:
        selected_demos = demo_suites.get(config.demo, demo_suites['core'])
    
    # Run selected demos
    for demo_func in selected_demos:
        demo_func(display, config.delay_multiplier)
        
        if not config.auto_advance:
            input("Press Enter to continue...")
        else:
            time.sleep(1.0 * config.delay_multiplier)
    
    # Completion message
    display.restore_defaults()
    display.write_both_lines("ALL DEMOS", "COMPLETED!")
    time.sleep(2 * config.delay_multiplier)
    
    logger.info("=== COMPREHENSIVE DEMO COMPLETED ===")

def main():
    """Main demo execution with CLI configuration."""
    parser = argparse.ArgumentParser(description="CD5220 VFD Display Demo")
    parser.add_argument('--port', default='/dev/tty.usbserial-A5XK3RJT', 
                       help='Serial port device')
    parser.add_argument('--baud', type=int, default=9600, 
                       help='Baud rate (default: 9600)')
    parser.add_argument('--fast', action='store_true', 
                       help='Reduce delays for experienced users')
    parser.add_argument('--demo', choices=['all', 'core', 'scrolling', 'config', 'convenience'], 
                       default='all', help='Run specific demo suite')
    parser.add_argument('--auto-advance', action='store_true',
                       help='Auto-advance between demos')
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
    
    logger.info("CD5220 Demo Suite")
    logger.info(f"Port: {args.port} | Baud: {args.baud} | Demo: {args.demo}")
    logger.info(f"Fast mode: {args.fast} | Auto-advance: {args.auto_advance}")
    
    try:
        with CD5220(
            args.port, 
            args.baud, 
            debug=args.verbose,
            auto_clear_mode_transitions=True,
            warn_on_mode_transitions=True,
            command_delay=args.command_delay
        ) as display:
            logger.info("Display initialized")
            run_comprehensive_demo(display, args)
            logger.info("Demo completed successfully!")
            
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
