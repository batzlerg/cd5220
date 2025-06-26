#!/usr/bin/env python3
"""Run built-in ASCII animations with optional console rendering."""

import argparse
import logging
import time
import inspect
from enum import Enum

from cd5220 import serial, CD5220, CD5220DisplayError, DiffAnimator
from animations import ANIMATIONS

logger = logging.getLogger('CD5220_Animations')


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CD5220 ASCII animation demo",
        allow_abbrev=False,
    )
    parser.add_argument('--animation', required=True,
                        choices=sorted(ANIMATIONS.keys()),
                        help='Animation to run')
    parser.add_argument('--port', default='/dev/tty.usbserial-A5XK3RJT',
                        help='Serial port device')
    parser.add_argument('--baud', type=int, default=9600,
                        help='Baud rate (default: 9600)')
    parser.add_argument('--render-console', dest='render_console',
                        action='store_true', default=True,
                        help='Render simulator output in the console')
    parser.add_argument('--no-render-console', dest='render_console',
                        action='store_false', help='Disable console rendering')
    parser.add_argument('--base-command-delay', type=float, default=0.0,
                        help='Base command delay in seconds')
    parser.add_argument('--mode-transition-delay', type=float, default=0.0,
                        help='Mode transition delay in seconds')
    parser.add_argument('--debug', action='store_true',
                        help='Enable verbose debug logging')

    # parse once to know which animation was chosen
    args, _ = parser.parse_known_args()

    anim_func = ANIMATIONS[args.animation]
    for param in list(inspect.signature(anim_func).parameters.values())[1:]:
        if param.default is inspect.Parameter.empty:
            parser.add_argument(
                f'--{param.name}', required=True, type=str
            )
        else:
            default = param.default
            if isinstance(default, Enum):
                parser.add_argument(f'--{param.name}', type=str, default=default.value)
            else:
                arg_type = type(default) if default is not None else float
                parser.add_argument(f'--{param.name}', type=arg_type, default=default)

    args = parser.parse_args()

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
            animator = DiffAnimator(
                display,
                sleep_fn=time.sleep,
                frame_sleep_fn=time.sleep,
                render_console=args.render_console,
            )
            func_kwargs = {}
            for name, param in inspect.signature(anim_func).parameters.items():
                if name == 'animator':
                    continue
                value = getattr(args, name)
                default = param.default
                if isinstance(default, Enum):
                    values = [v.strip() for v in value.split(',')]
                    enums = [type(default)(v) for v in values]
                    func_kwargs[name] = enums if len(enums) > 1 else enums[0]
                else:
                    func_kwargs[name] = value
            logger.info(
                f"Starting '{args.animation}' animation (press Ctrl+C to stop)"
            )
            anim_func(animator, **func_kwargs)
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
