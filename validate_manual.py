import argparse
import os
import sys
import time
from cd5220 import CD5220

"""
temporary script for manual testing of the simulator output via the time-honored tradition of "guess and check"
"""

# character placeholders to make it clearer what's rendered and what's left blank.
# these characters are not supported by the display itself, intentionally
SPACE_PLACEHOLDER = "\xb7"  # middle dot
SCROLL_PLACEHOLDER = "\u2190"  # left arrow showing scroll direction


def format_line(line: str) -> str:
    """Return display line with spaces shown explicitly."""
    return line.replace(" ", SPACE_PLACEHOLDER)


def prompt_match(case_id: str) -> bool:
    """Prompt the user to confirm a match."""
    while True:
        resp = input(f"\nCase {case_id} - does the hardware match the simulator? [y/n]: ").strip().lower()
        if resp in {"y", "n"}:
            return resp == "y"
        print("Please enter 'y' or 'n'.")


def print_frame(line1: str, line2: str, disp: CD5220) -> None:
    """Print expected display frame with state information."""
    print("\nExpected display state:")
    print(format_line(line1))
    print(format_line(line2))
    print(
        f"Brightness={disp.simulator.brightness} "
        f"CursorVisible={disp.simulator.cursor_visible}"
    )


def show_expected_state(disp: CD5220) -> None:
    line1, line2 = disp.simulator.get_display()
    if not disp.simulator.display_on:
        line1 = " " * disp.DISPLAY_WIDTH
        line2 = " " * disp.DISPLAY_WIDTH
    print_frame(line1, line2, disp)


def validate_basic_strings(disp: CD5220):
    disp.clear_display()
    disp.write_upper_line("HELLO")
    disp.write_lower_line("WORLD")
    show_expected_state(disp)



def validate_cursor_and_text(disp: CD5220):
    disp.clear_display()
    disp.set_cursor_position(5, 1)
    disp.write_at_cursor("A")
    disp.cursor_move_right()
    disp.write_at_cursor("B")
    show_expected_state(disp)



def validate_scroll_marquee(disp: CD5220):
    disp.clear_display()
    text = "SCROLLING"
    disp.scroll_marquee(text)
    line1, line2 = disp.simulator.get_display()
    indicator = text + SCROLL_PLACEHOLDER * (disp.DISPLAY_WIDTH - len(text))
    print_frame(indicator, line2, disp)
    time.sleep(3)



def validate_viewport(disp: CD5220):
    disp.clear_display()
    disp.set_window(1, 4, 10)
    disp.enter_viewport_mode()
    disp.write_viewport(1, "VIEWPORTTEXT")
    show_expected_state(disp)



def validate_command_interaction(disp: CD5220):
    disp.clear_display()
    disp.write_upper_line("START")
    disp.set_window(2, 8, 15)
    disp.enter_viewport_mode()
    disp.write_viewport(2, "ABCDE")
    disp.cancel_current_line()
    text = "SEQ COMPLETE - SCROLL"
    disp.scroll_marquee(text)
    line1, line2 = disp.simulator.get_display()
    indicator = text + SCROLL_PLACEHOLDER * (disp.DISPLAY_WIDTH - len(text))
    print_frame(indicator, line2, disp)
    time.sleep(3)


def validate_state_commands(disp: CD5220):
    """Validate brightness, display on/off, and cursor visibility commands."""
    disp.clear_display()
    disp.write_both_lines("STATE TEST", "CURSOR VISIBLE")
    disp.set_brightness(2)
    disp.cursor_on()
    disp.display_off()
    time.sleep(1)
    disp.display_on()
    show_expected_state(disp)


def validate_display_off(disp: CD5220):
    """Show blank output after turning the display off."""
    disp.clear_display()
    disp.write_both_lines("12345678901234567890", "ABCDEFGHIJKLMNOPQRST")
    disp.display_off()
    show_expected_state(disp)



def main():
    parser = argparse.ArgumentParser(description="Run manual hardware validation tests.")
    parser.add_argument("port", nargs="?", default=os.environ.get("VALIDATE_PORT"),
                        help="Serial port connected to the CD5220 display")
    parser.add_argument("--console", action="store_true", help="Render console output during tests")
    parser.add_argument("--console-verbose", action="store_true", help="Show frames when commands have no visual effect")
    parser.add_argument("--case", help="Run a single validation case by ID")
    args = parser.parse_args()

    if not args.port:
        parser.error("Serial port required (pass as argument or set VALIDATE_PORT)")

    cases = {
        "BASIC": ("basic string writes", validate_basic_strings),
        "CURSOR": ("cursor and text", validate_cursor_and_text),
        "SCROLL": ("scroll marquee", validate_scroll_marquee),
        "VIEW": ("viewport text", validate_viewport),
        "SEQ": ("command sequence interaction", validate_command_interaction),
        "STATE": ("brightness/display/cursor", validate_state_commands),
        "OFF": ("display off", validate_display_off),
    }

    if args.case:
        case_key = args.case.upper()
        if case_key not in cases:
            parser.error(f"Unknown case ID {args.case}. Choices: {', '.join(cases)}")
        selected = {case_key: cases[case_key]}
    else:
        selected = cases

    disp = CD5220.create_validation_mode(
        args.port,
        render_console=args.console,
        console_verbose=args.console_verbose,
        debug=False,
    )
    results = {}
    try:
        for cid, (desc, func) in selected.items():
            print(f"\nRunning case {cid}: {desc}")
            func(disp)
            results[cid] = prompt_match(cid)

        # Clear the display before showing the final table so the last thing on
        # screen is the summary and not a debug log from the clear.
        disp.clear_display()

        # Format results in a neat table
        print("\nValidation Results:")
        header = f"{'ID':<6} {'Description':<30} Result"
        print(header)
        print("-" * len(header))
        for cid, (desc, _) in selected.items():
            status = "PASS" if results.get(cid) else "FAIL"
            print(f"{cid:<6} {desc:<30} {status}")
        all_pass = all(results.values())
        print("\nOverall:", "ALL MATCHED" if all_pass else "MISMATCHES FOUND")
    finally:
        if disp.ser:
            disp.ser.close()
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
