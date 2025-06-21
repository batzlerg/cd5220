#!/usr/bin/env python3
"""
CD5220 VFD Display Comprehensive Demo with Smart Mode Management

Demonstrates all documented modes and the smart mode management system:
- Normal Mode: Full cursor control and ESC commands  
- String Mode: Fast line writing (ESC Q A/B)
- Scroll Mode: Continuous scrolling (ESC Q D/C)
- Smart transitions: Automatic mode management

Hardware Requirements:
- CD5220 VFD display (2x20 characters)
- RS232 connection at 9600 baud
- Display configured for PTC mode (DIP switches)

Timing Considerations:
- Scroll refresh rate: ~1Hz (display-dependent)
- Mode transitions require settling time
- Visual confirmation requires adequate pause
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
        self.BRIGHTNESS_PAUSE = 1.5 * delay_multiplier
        self.MODE_TRANSITION_DELAY = 0.3 * delay_multiplier
        self.VISUAL_CONFIRMATION_TIME = 2.0 * delay_multiplier
        self.SCROLL_OBSERVATION_TIME = 12.0 * delay_multiplier
        
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
    """Demonstrate the smart mode management system."""
    
    # Test 1: String mode to cursor control (auto-clear)
    fixture.show_banner("TEST 1: AUTO CLEAR", "STRING → CURSOR")
    display.write_upper_line_string("STRING MODE TEXT")
    logger.info(f"Current mode: {display.current_mode.value}")
    
    # This should trigger auto-clear and mode transition
    display.cursor_on()
    display.set_cursor_position(1, 2)
    display.write_at_cursor("CURSOR WORKS!")
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    display.cursor_off()
    
    # Test 2: Manual mode control demonstration
    fixture.show_banner("TEST 2: MANUAL", "MODE CONTROL")
    display.write_upper_line_string("MANUAL CONTROL")
    logger.info(f"Before clear: {display.current_mode.value}")
    display.clear_display()
    logger.info(f"After clear: {display.current_mode.value}")
    display.write_positioned("CLEARED MANUALLY", 1, 1)
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)

def demo_normal_mode_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate all normal mode functionality."""
    
    # Test brightness control
    fixture.show_banner("BRIGHTNESS DEMO", "LEVELS 1-4")
    for level in range(1, 5):
        display.set_brightness(level)
        display.write_positioned(f"BRIGHTNESS: {level}/4", 1, 1)
        display.write_positioned("NORMAL MODE", 1, 2)
        time.sleep(fixture.BRIGHTNESS_PAUSE)
    
    # Test cursor functionality  
    fixture.show_banner("CURSOR DEMO", "POSITIONING")
    display.clear_display()
    display.write_positioned("CURSOR DEMO", 1, 1)
    display.cursor_on()
    
    # Move cursor through positions
    positions = [(1, 2), (5, 2), (10, 2), (15, 2), (20, 2)]
    for col, row in positions:
        display.set_cursor_position(col, row)
        time.sleep(0.5 * fixture.delay_multiplier)
    
    # Test writing at cursor
    display.set_cursor_position(1, 2)
    display.write_at_cursor("Hello ")
    time.sleep(0.5 * fixture.delay_multiplier)
    display.write_at_cursor("World!")
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    display.cursor_off()
    
    # Test display modes with proper restoration
    fixture.show_banner("DISPLAY MODES", "TESTING")
    
    display.set_overwrite_mode()
    display.write_positioned("OVERWRITE MODE", 1, 1)
    display.write_positioned("ACTIVE", 1, 2)
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    
    display.set_vertical_scroll_mode()
    display.write_positioned("VERTICAL SCROLL", 1, 1)
    display.write_positioned("MODE ACTIVE", 1, 2)
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    
    display.set_horizontal_scroll_mode()
    display.write_positioned("HORIZONTAL MODE", 1, 1)
    display.write_positioned("ACTIVE", 1, 2)
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    
    # Restore overwrite mode before exit
    display.set_overwrite_mode()

def demo_string_mode_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate string mode functionality."""
    
    # Test basic string writing
    fixture.show_banner("STRING MODE", "FAST WRITING")
    display.write_upper_line_string("STRING MODE DEMO")
    display.write_lower_line_string("FAST LINE WRITING")
    logger.info(f"Current mode: {display.current_mode.value}")
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test both lines together
    fixture.show_banner("BOTH LINES", "TOGETHER")
    display.write_both_lines_string("BOTH LINES", "UPDATED TOGETHER")
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test text handling (truncation)
    fixture.show_banner("TEXT HANDLING", "AUTO TRUNCATE")
    display.write_upper_line_string("THIS IS A VERY LONG LINE THAT EXCEEDS TWENTY CHARACTERS")
    display.write_lower_line_string("TRUNCATED TO 20")
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
    
    # Test automatic padding
    fixture.show_banner("AUTO PADDING", "SHORT TEXT")
    display.write_upper_line_string("SHORT")
    display.write_lower_line_string("PADDED")
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)

def demo_scroll_mode_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate scroll mode functionality with proper timing."""
    
    # Test upper line scrolling with hardware-aware timing
    fixture.show_banner("SCROLL DEMO", "UPPER LINE")
    display.clear_display()
    display.write_positioned("SCROLL DEMO", 1, 2)  # Static text on line 2
    
    scroll_text = "CONTINUOUS SCROLLING TEXT ON UPPER LINE - OBSERVE MULTIPLE CYCLES"
    display.scroll_upper_line(scroll_text)
    logger.info(f"Current mode: {display.current_mode.value}")
    
    # Calculate appropriate observation time for the text length
    observation_time = max(fixture.SCROLL_OBSERVATION_TIME, len(scroll_text) / display.SCROLL_REFRESH_RATE * 0.6)
    logger.info(f"Observing scroll for {observation_time:.1f} seconds")
    time.sleep(observation_time)
    
    # Test lower line scrolling (stops upper scroll)
    fixture.show_banner("LOWER SCROLL", "REPLACES UPPER", duration=1.0)
    display.scroll_lower_line("LOWER LINE SCROLLING - NOTICE HOW THIS STOPS UPPER SCROLL")
    time.sleep(observation_time * 0.8)  # Slightly shorter for variety
    
    # Demonstrate cancel_current_line() instead of clear_display()
    logger.info("Stopping scroll with cancel_current_line()")
    display.cancel_current_line()
    logger.info(f"Mode after cancel: {display.current_mode.value}")
    
    # Show that display content is preserved (unlike clear_display)
    display.write_positioned("CANCELLED, NOT", 1, 1)
    display.write_positioned("CLEARED", 1, 2)
    time.sleep(fixture.VISUAL_CONFIRMATION_TIME)

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
        
        try:
            # This should fail without auto-clear
            display.cursor_on()
            logger.error("ERROR: Should have failed!")
        except CD5220DisplayError as e:
            logger.info(f"Expected error caught: {e}")
            fixture.show_banner("ERROR CAUGHT", "AS EXPECTED")
            time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
        
        # Manual clear should work
        display.clear_display()
        display.cursor_on()
        display.set_cursor_position(1, 2)
        display.write_at_cursor("MANUAL CLEAR OK")
        display.cursor_off()
        time.sleep(fixture.VISUAL_CONFIRMATION_TIME)
        
    finally:
        # Restore original settings
        display.auto_clear_mode_transitions = original_auto_clear
        display.warn_on_mode_transitions = original_warn
        logger.info("Restored original configuration")

def demo_convenience_features(display: CD5220, fixture: CD5220DemoFixture):
    """Demonstrate convenience methods."""
    
    # Test display_message
    fixture.show_banner("CONVENIENCE", "METHODS")
    display.display_message("This is a long message that will wrap automatically", 
                          duration=fixture.VISUAL_CONFIRMATION_TIME, mode="string")
    
    display.display_message("SHORTER MESSAGE", 
                          duration=fixture.VISUAL_CONFIRMATION_TIME, mode="normal")
    
    # Test rapid updates (staying in string mode)
    fixture.show_banner("RAPID UPDATES", "STRING MODE")
    for i in range(5):
        display.write_both_lines_string(f"COUNTER: {i+1}", f"RAPID UPDATE #{i+1}")
        time.sleep(0.5 * fixture.delay_multiplier)

def run_comprehensive_demo(display: CD5220, config):
    """Run a comprehensive demo showing all capabilities."""
    logger.info("=== CD5220 COMPREHENSIVE DEMO ===")
    
    fixture = CD5220DemoFixture(display, config.delay_multiplier)
    
    # Welcome message
    display.display_message("CD5220 SMART MODE DEMO - STARTING ALL DEMOS", 
                          duration=3 * config.delay_multiplier, mode="string")
    
    # Demo suites based on CLI selection
    demo_suites = {
        'modes': [
            (demo_normal_mode_features, "NORMAL MODE"),
            (demo_string_mode_features, "STRING MODE"),
            (demo_scroll_mode_features, "SCROLL MODE")
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
    
    display.write_both_lines_string("SMART MODE DEMO", "FINISHED!")
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
    parser.add_argument('--demo', choices=['all', 'modes', 'smart', 'config', 'convenience'], 
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
    
    logger.info("CD5220 Smart Mode Management Demo Suite")
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
