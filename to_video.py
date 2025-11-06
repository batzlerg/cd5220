#!/usr/bin/env python3
"""
VFD Animation to MP4 Renderer
Renders cd5220 animations to video files with proper spacing
"""

import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random
import math
import argparse

# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_FPS = 6
DEFAULT_DURATION = 10.0
CANVAS_WIDTH = 640   # Total canvas width
CANVAS_HEIGHT = 200  # Increased from 160 to prevent bottom clipping
LEFT_MARGIN = 40     # Left padding for balanced appearance
TOP_MARGIN = 45      # Top padding
CHAR_AREA_WIDTH = CANVAS_WIDTH - (LEFT_MARGIN * 2)  # 560px for 20 chars
CHAR_WIDTH = CHAR_AREA_WIDTH / 20  # 28px per character
LINE_SPACING = 70    # Vertical distance between line tops
FONT_SIZE = 28       # Font size to fit in 28px char width
FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'

# ============================================================================
# FRAME CAPTURING DISPLAY
# ============================================================================

class FrameCapturingDisplay:
    """Mock display that captures frames for video rendering"""

    def __init__(self):
        self.frames = []
        self.current = [' ' * 20, ' ' * 20]

    def write_positioned(self, char: str, x: int, y: int):
        """CD5220 uses 1-based coordinates"""
        if 1 <= x <= 20 and 1 <= y <= 2:
            line_idx = y - 1
            char_idx = x - 1
            line = list(self.current[line_idx])
            line[char_idx] = char
            self.current[line_idx] = ''.join(line)

    def clear_display(self):
        self.current = [' ' * 20, ' ' * 20]

    def capture_frame(self):
        """Store current frame state"""
        self.frames.append((self.current[0], self.current[1]))

# ============================================================================
# ANIMATION EXECUTION
# ============================================================================

def execute_animation(code: str, func_name: str, duration: float, fps: int):
    """Execute animation and capture frames"""

    # Clean code
    if code.startswith('ℹ') or code.startswith('✓') or code.startswith('✗'):
        raise ValueError("Corrupt file (emoji prefix)")

    code = code.replace('``````', '')

    display = FrameCapturingDisplay()

    try:
        from cd5220 import DiffAnimator
    except ImportError as e:
        raise ImportError(f"cd5220 not found: {e}")

    animator = DiffAnimator(display, frame_rate=fps)

    # Intercept write_frame - capture but don't render
    def capturing_write(line1: str, line2: str):
        display.current = [line1[:20].ljust(20), line2[:20].ljust(20)]
        display.capture_frame()

    animator.write_frame = capturing_write

    # Execute animation
    namespace = {
        'DiffAnimator': DiffAnimator,
        'animator': animator,
        'random': random,
        'math': math
    }

    exec(code, namespace)

    if func_name not in namespace:
        raise ValueError(f"Function {func_name} not found")

    anim_func = namespace[func_name]
    anim_func(animator, duration=duration)

    return display.frames

# ============================================================================
# VIDEO RENDERING
# ============================================================================

def render_frames_to_video(frames, output_path: Path, fps: int):
    """Render frames to MP4 using FFmpeg pipe"""

    if not frames:
        raise ValueError("No frames to render")

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    # Start FFmpeg process
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'rgb24',
        '-s', f'{CANVAS_WIDTH}x{CANVAS_HEIGHT}',
        '-r', str(fps),
        '-i', '-',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-crf', '18',
        '-loglevel', 'error',
        str(output_path)
    ]

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        for line1, line2 in frames:
            img = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), color='black')
            draw = ImageDraw.Draw(img)

            # Draw line 1 with balanced left margin
            for i, char in enumerate(line1):
                x = int(LEFT_MARGIN + (i * CHAR_WIDTH))
                draw.text((x, TOP_MARGIN), char, fill='#00FFFF', font=font)

            # Draw line 2 with balanced left margin
            for i, char in enumerate(line2):
                x = int(LEFT_MARGIN + (i * CHAR_WIDTH))
                draw.text((x, TOP_MARGIN + LINE_SPACING), char, fill='#00FFFF', font=font)

            # Write frame to FFmpeg stdin
            try:
                proc.stdin.write(img.tobytes())
            except BrokenPipeError:
                break

        # Close stdin properly
        try:
            proc.stdin.close()
        except:
            pass

        # Wait for FFmpeg to finish
        proc.wait(timeout=30)

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode() if proc.stderr else ''
            raise RuntimeError(f"FFmpeg failed (code {proc.returncode}): {stderr}")

    except Exception as e:
        try:
            proc.kill()
        except:
            pass
        raise

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Render VFD animations to MP4')
    parser.add_argument('-d', '--duration', type=float, default=DEFAULT_DURATION)
    parser.add_argument('--fps', type=int, default=DEFAULT_FPS)
    parser.add_argument('--force', action='store_true', help='Re-render existing videos')
    parser.add_argument('files', nargs='*', help='Specific animation files')

    args = parser.parse_args()

    # Check FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ ffmpeg not found. Install: sudo apt-get install ffmpeg")
        sys.exit(1)

    # Check font
    if not Path(FONT_PATH).exists():
        print(f"✗ Font not found: {FONT_PATH}")
        sys.exit(1)

    print(f"ℹ Using font: {FONT_PATH}")
    print(f"ℹ Canvas: {CANVAS_WIDTH}x{CANVAS_HEIGHT}px with {LEFT_MARGIN}px side margins")

    # Find animations
    gen_dir = Path('generated_animations')
    if not gen_dir.exists():
        print(f"✗ Directory not found: {gen_dir}")
        sys.exit(1)

    if args.files:
        anim_files = [gen_dir / f for f in args.files]
    else:
        anim_files = sorted(gen_dir.glob('anim_*.py'))

    print(f"ℹ Found {len(anim_files)} animations")

    videos_dir = gen_dir / 'videos'
    videos_dir.mkdir(exist_ok=True)

    success = 0
    skipped = 0
    failed = 0

    for py_file in anim_files:
        func_name = py_file.stem
        video_path = videos_dir / f"{func_name}.mp4"

        if video_path.exists() and not args.force:
            skipped += 1
            continue

        print(f"ℹ Rendering {func_name}...")

        try:
            code = py_file.read_text()
            frames = execute_animation(code, func_name, args.duration, args.fps)

            if not frames:
                print(f"✗ No frames captured")
                failed += 1
                continue

            render_frames_to_video(frames, video_path, args.fps)
            print(f"✓ Saved {video_path} ({len(frames)} frames)")
            success += 1

        except Exception as e:
            print(f"✗ Failed: {e}")
            failed += 1

    print(f"\n✓ Success: {success} | ⊘ Skipped: {skipped} | ✗ Failed: {failed}")

if __name__ == '__main__':
    main()
