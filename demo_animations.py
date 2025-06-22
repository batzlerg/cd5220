#!/usr/bin/env python3
"""Run built-in ASCII animations with optional console rendering."""

import argparse
import logging
import time
from cd5220 import serial
from cd5220 import CD5220, CD5220DisplayError, CD5220ASCIIAnimations

logger = logging.getLogger('CD5220_Animations')


def main() -> None:
    parser = argparse.ArgumentParser(description="CD5220 ASCII animation demo")
    parser.add_argument('--port', default='/dev/tty.usbserial-A5XK3RJT',
                        help='Serial port device')
    parser.add_argument('--baud', type=int, default=9600,
                        help='Baud rate (default: 9600)')
    parser.add_argument('--fast', action='store_true',
                        help='Reduce delays for experienced users')
    parser.add_argument('--render-console', dest='render_console',
                        action='store_true', default=True,
                        help='Render simulator output in the console')
    parser.add_argument('--no-render-console', dest='render_console',
                        action='store_false', help='Disable console rendering')
    parser.add_argument('--auto-advance', dest='auto_advance', action='store_true',
                        default=True,
                        help='Auto-advance between animations (default: enabled)')
    parser.add_argument('--no-auto-advance', dest='auto_advance', action='store_false',
                        help='Wait for Enter before exiting')
    parser.add_argument('--base-command-delay', type=float, default=0.0,
                        help='Base command delay in seconds')
    parser.add_argument('--mode-transition-delay', type=float, default=0.0,
                        help='Mode transition delay in seconds')
    parser.add_argument('--debug', action='store_true',
                        help='Enable verbose debug logging')

    args = parser.parse_args()

    args.delay_multiplier = 0.3 if args.fast else 1.0

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s %(levelname)-8s [ANIM] %(message)s',
        datefmt='%H:%M:%S',
        force=True,
    )

    try:
        with CD5220(
            args.port,
            args.baud,
            debug=args.debug,
            auto_clear_mode_transitions=True,
            warn_on_mode_transitions=True,
            base_command_delay=args.base_command_delay,
            mode_transition_delay=args.mode_transition_delay,
        ) as display:
            animations = CD5220ASCIIAnimations(
                display,
                sleep_fn=time.sleep,
                frame_sleep_fn=time.sleep,
                render_console=args.render_console,
            )
            logger.info("Running startup sequence")
            animations.play_startup_sequence()
            logger.info("Running animation cycle")
            animations.play_demo_cycle()
            if not args.auto_advance:
                input("Press Enter to exit...")
    except CD5220DisplayError as e:
        logger.error(f"Display error: {e}")
    except serial.SerialException as e:
        logger.error(f"Serial error: {e}")
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception:
        logger.exception("Unexpected error occurred:")


if __name__ == '__main__':
    main()
