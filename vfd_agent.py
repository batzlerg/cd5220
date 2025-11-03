#!/usr/bin/env python3
"""
VFD Animation Agent - Production v1.0 FINAL
Autonomous AI art generator for CD5220 VFD display
Zero regressions, all fixes applied
"""

import sys
import os
import json
import random
import time
import argparse
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime
import requests

# Add cd5220 to path
sys.path.insert(0, str(Path.home() / 'cd5220'))
from cd5220 import CD5220, DiffAnimator

# ============================================================================
# CONFIGURATION
# ============================================================================

VFD_DEVICE = os.getenv('VFD_DEVICE', '/dev/ttyUSB0')
VFD_BAUDRATE = 9600
OLLAMA_API_BASE = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')
MIN_INTERVAL = int(os.getenv('MIN_INTERVAL', '15'))  # Minimum wait between animations
MAX_GENERATION_TIME = int(os.getenv('MAX_GENERATION_TIME', '120'))  # 2min timeout
ANIMATION_DURATION = float(os.getenv('ANIMATION_DURATION', '10.0'))
FRAME_RATE = 6
MAX_RETRIES = 3

# ============================================================================
# COLORS
# ============================================================================

class C:
    INFO = '\033[0;36m'
    OK = '\033[0;32m'
    ERR = '\033[0;31m'
    WARN = '\033[1;33m'
    DEBUG = '\033[0;35m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

VERBOSE = False

def info(msg: str): print(f"{C.INFO}ℹ{C.RESET} {msg}", file=sys.stderr)
def ok(msg: str): print(f"{C.OK}✓{C.RESET} {msg}", file=sys.stderr)
def err(msg: str): print(f"{C.ERR}✗{C.RESET} {msg}", file=sys.stderr)
def warn(msg: str): print(f"{C.WARN}⚠{C.RESET} {msg}", file=sys.stderr)
def debug(msg: str):
    if VERBOSE:
        print(f"{C.DEBUG}[DEBUG]{C.RESET} {msg}", file=sys.stderr)

def header(msg: str):
    print(f"\n{C.BOLD}{'='*40}{C.RESET}", file=sys.stderr)
    print(f"{C.BOLD}{msg}{C.RESET}", file=sys.stderr)
    print(f"{C.BOLD}{'='*40}{C.RESET}", file=sys.stderr)

# ============================================================================
# SYSTEM PROMPT
# ============================================================================

PROMPT = """Create an ANIMATED function for a 20x2 char VFD display. MOTION is key!

RULES:
1. def FUNCNAME(animator: DiffAnimator, duration: float = 10.0)
2. Every frame: animator.write_frame(line1_20char, line2_20char)
3. Every frame: animator.frame_sleep(1.0/animator.frame_rate)
4. Pad to 20: text[:20].ljust(20)
5. frame_count = int(duration * animator.frame_rate)
6. Use 'frame' variable for MOTION (scrolling, bouncing, fading, etc)
7. Common imports available: random, math
8. Output ONLY Python code - NO markdown

EXAMPLES WITH MOTION:

# Scrolling text
def scroll_text(animator: DiffAnimator, duration: float = 10.0):
    text = "HELLO WORLD  "
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        offset = frame % len(text)
        line1 = (text[offset:] + text)[:20].ljust(20)
        animator.write_frame(line1, " " * 20)
        animator.frame_sleep(1.0 / animator.frame_rate)

# Bouncing ball
def bounce_ball(animator: DiffAnimator, duration: float = 10.0):
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        pos = int(abs(10 * math.sin(frame * 0.3)))
        line1 = (" " * pos + "O" + " " * (19-pos))[:20].ljust(20)
        animator.write_frame(line1, " " * 20)
        animator.frame_sleep(1.0 / animator.frame_rate)

# Pulsing stars
def pulse_stars(animator: DiffAnimator, duration: float = 10.0):
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        intensity = int(3 + 2 * math.sin(frame * 0.2))
        chars = [".", "*", "x", "X", "#"]
        char = chars[min(intensity, len(chars)-1)]
        line1 = (char + " ") * 10
        animator.write_frame(line1[:20].ljust(20), " " * 20)
        animator.frame_sleep(1.0 / animator.frame_rate)

OUTPUT ONLY THE FUNCTION CODE."""

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class State:
    """Persistent state tracker"""
    
    def __init__(self, state_file: Path):
        self.file = state_file
        self.data = self._load()
    
    def _load(self) -> Dict:
        if self.file.exists():
            try:
                with open(self.file) as f:
                    return json.load(f)
            except:
                return {'generations': [], 'success': 0, 'failure': 0}
        return {'generations': [], 'success': 0, 'failure': 0}
    
    def save(self, func: str, desc: str, status: str, error: str = ""):
        self.data['generations'].append({
            'timestamp': int(time.time()),
            'function': func,
            'description': desc,
            'status': status,
            'error': error[:200] if error else ""
        })
        self.data[status] = self.data.get(status, 0) + 1
        self.data['generations'] = self.data['generations'][-50:]
        
        try:
            with open(self.file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            warn(f"Failed to save state: {e}")
    
    def stats(self) -> str:
        s = self.data.get('success', 0)
        f = self.data.get('failure', 0)
        return f"✓{s} ✗{f}"
    
    def last_errors(self, n: int = 3) -> str:
        errors = [g for g in self.data['generations'][-10:] if g.get('error')]
        if not errors:
            return ""
        recent = errors[-n:]
        return "\n".join([f"- {e['error']}" for e in recent])

# ============================================================================
# IDEA GENERATOR
# ============================================================================

def generate_idea() -> str:
    """Generate random animation concept"""
    patterns = ['scroll', 'pulse', 'bounce', 'fade', 'wave', 'blink', 'sweep', 'spin']
    elements = ['text', 'dots', 'stars', 'lines', 'bars', 'arrow', 'box', 'waves']
    styles = ['simple', 'smooth', 'fast', 'slow', 'random', 'steady']
    return f"{random.choice(patterns)} {random.choice(elements)} {random.choice(styles)}"

# ============================================================================
# CODE CLEANER
# ============================================================================

def clean_code(raw_code: str, func_name: str) -> Tuple[Optional[str], str]:
    """Aggressively clean LLM output"""
    
    debug(f"Raw code length: {len(raw_code)} chars")
    debug(f"First 100 chars: {repr(raw_code[:100])}")
    
    # Remove ALL markdown
    code = raw_code
    code = code.replace('`'*3 + 'python', '')
    code = code.replace('`'*3, '')
    code = code.strip()
    
    debug(f"After markdown removal: {len(code)} chars")
    
    # Find function definition
    lines = code.split('\n')
    func_start = -1
    
    for i, line in enumerate(lines):
        if line.strip().startswith(f'def {func_name}('):
            func_start = i
            break
    
    if func_start == -1:
        for i, line in enumerate(lines):
            if line.strip().startswith('def ') and 'animator' in line.lower():
                warn(f"Found function but name mismatch at line {i}")
                func_start = i
                break
    
    if func_start == -1:
        return None, f"No function definition found. First 200 chars: {code[:200]}"
    
    # Extract function
    func_lines = lines[func_start:]
    func_code = '\n'.join(func_lines)
    
    debug(f"Extracted function: {len(func_code)} chars, {len(func_lines)} lines")
    
    # Build complete module
    full_code = f"from cd5220 import DiffAnimator\n\n{func_code}\n"
    
    # Sanity checks
    if 'write_frame' not in full_code:
        return None, "Missing animator.write_frame() call"
    if 'frame_sleep' not in full_code:
        return None, "Missing animator.frame_sleep() call"
    if len(full_code) < 100:
        return None, f"Code too short ({len(full_code)} chars)"
    
    return full_code, ""

# ============================================================================
# CODE GENERATOR
# ============================================================================

def generate_code(desc: str, func_name: str, attempt: int, prev_errors: str) -> Tuple[Optional[str], str]:
    """Generate animation code via Ollama API"""
    
    debug(f"Attempt {attempt}: generating '{desc}' as {func_name}")
    info(f"Creating: {desc}")
    
    # Build context-aware prompt
    retry_context = ""
    if attempt > 1:
        retry_context = f"""
PREVIOUS ATTEMPT FAILED:
{prev_errors}

FIX: Output ONLY raw Python code. NO markdown. NO explanations."""
    
    user_prompt = f"""Create animation: {desc}
Function name: {func_name}
{retry_context}

Output ONLY the Python function code starting with 'def {func_name}'."""
    
    full_prompt = f"{PROMPT}\n\n{user_prompt}"
    
    payload = {
        'model': MODEL,
        'prompt': full_prompt,
        'stream': False,
        'options': {
            'temperature': 0.7 - (attempt * 0.1),
            'num_predict': 600,
            'stop': ['\n\ndef ', '\nif __name__']
        }
    }
    
    try:
        debug("Calling Ollama API...")
        resp = requests.post(
            f"{OLLAMA_API_BASE}/api/generate",
            json=payload,
            timeout=MAX_GENERATION_TIME
        )
        resp.raise_for_status()
        
        data = resp.json()
        raw_code = data.get('response', '')
        
        if not raw_code:
            return None, "Empty API response"
        
        debug(f"API returned {len(raw_code)} chars")
        
        return clean_code(raw_code, func_name)
        
    except Exception as e:
        return None, f"API error: {str(e)[:100]}"

# ============================================================================
# VALIDATOR
# ============================================================================

def validate_syntax(code: str) -> Tuple[bool, str]:
    """Validate Python syntax"""
    try:
        compile(code, '<string>', 'exec')
        return True, ""
    except SyntaxError as e:
        error_msg = f"Line {e.lineno}: {e.msg}"
        if e.text:
            error_msg += f" -> {e.text.strip()}"
        return False, error_msg

# ============================================================================
# EXECUTOR
# ============================================================================

def execute_animation(code: str, func_name: str) -> Tuple[bool, str]:
    """Execute animation on hardware"""
    try:
        import random
        import math
        namespace = {
            'DiffAnimator': DiffAnimator,
            'random': random,
            'math': math
        }
        
        # Load code
        exec(code, namespace)
        
        if func_name not in namespace:
            return False, f"Function {func_name} not in namespace"
        
        # Connect to display
        debug(f"Connecting to {VFD_DEVICE}...")
        display = CD5220(VFD_DEVICE, baudrate=VFD_BAUDRATE)
        animator = DiffAnimator(display, frame_rate=FRAME_RATE, render_console=False)
        
        # Run animation
        info(f"▶ Running {func_name} for {ANIMATION_DURATION}s...")
        try:
            namespace[func_name](animator, duration=ANIMATION_DURATION)
            animator.clear_display()
            return True, ""
        except KeyboardInterrupt:
            warn("Interrupted by user")
            animator.clear_display()
            return False, "User interrupted"
        except Exception as e:
            animator.clear_display()
            return False, f"{type(e).__name__}: {str(e)}"
    
    except Exception as e:
        return False, f"Exec error: {type(e).__name__}: {str(e)}"

# ============================================================================
# MAIN GENERATION LOOP
# ============================================================================

def generate_and_run(output_dir: Path, state: State, gen_num: int, user_desc: Optional[str] = None) -> bool:
    """Generate and execute one animation"""
    header(f"Generation #{gen_num}")
    
    desc = user_desc if user_desc else generate_idea()
    func_name = f"anim_{int(time.time())}"
    code_file = output_dir / f"{func_name}.py"
    
    info(f"Concept: {desc}")
    
    all_errors = []
    
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            warn(f"Retry {attempt}/{MAX_RETRIES}")
        
        prev_errors = "\n".join(all_errors[-2:]) if all_errors else ""
        
        # Generate
        code, gen_error = generate_code(desc, func_name, attempt, prev_errors)
        
        if not code:
            err(f"Generation failed: {gen_error}")
            all_errors.append(f"Gen: {gen_error}")
            continue
        
        # Save
        try:
            code_file.write_text(code)
            ok(f"Saved: {code_file.name}")
        except Exception as e:
            err(f"Save failed: {e}")
            all_errors.append(f"Save: {e}")
            continue
        
        # Preview
        info("Preview:")
        lines = code.split('\n')
        for i, line in enumerate(lines[:10], 1):
            print(f"  {i:2d}| {line}", file=sys.stderr)
        if len(lines) > 10:
            print(f"  ...({len(lines)-10} more lines)", file=sys.stderr)
        
        # Validate
        valid, syntax_error = validate_syntax(code)
        if not valid:
            err(f"Syntax error: {syntax_error}")
            all_errors.append(f"Syntax: {syntax_error}")
            continue
        
        ok("Syntax OK")
        
        # Execute
        success, exec_error = execute_animation(code, func_name)
        if success:
            ok("✓ Animation completed successfully!")
            state.save(func_name, desc, 'success')
            return True
        else:
            err(f"Execution failed: {exec_error}")
            all_errors.append(f"Exec: {exec_error}")
    
    # All retries failed
    final_error = " | ".join(all_errors[-3:])
    err(f"Failed after {MAX_RETRIES} attempts")
    state.save(func_name, desc, 'failure', final_error)
    return False

# ============================================================================
# MODES
# ============================================================================

def continuous_mode(output_dir: Path, state: State):
    """Continuous generation with smart timing"""
    header("Continuous Mode - Autonomous AI Art")
    info(f"Device:{VFD_DEVICE} | Model:{MODEL}")
    info(f"Min interval:{MIN_INTERVAL}s | Animation:{ANIMATION_DURATION}s")
    info("Press Ctrl+C to stop")
    
    gen_num = 0
    while True:
        gen_num += 1
        
        # Track generation time
        gen_start = time.time()
        generate_and_run(output_dir, state, gen_num)
        gen_elapsed = time.time() - gen_start
        
        info(f"Stats: {state.stats()}")
        
        if VERBOSE:
            recent_errors = state.last_errors()
            if recent_errors:
                debug("Recent error patterns:")
                for line in recent_errors.split('\n'):
                    debug(f"  {line}")
        
        # Smart wait: min 15s, but generation already took time
        wait_time = max(0, MIN_INTERVAL - gen_elapsed)
        
        if wait_time > 0:
            info(f"Next in {wait_time:.1f}s...")
            try:
                time.sleep(wait_time)
            except KeyboardInterrupt:
                info("\nStopped by user")
                break
        else:
            info("Starting next generation immediately...")

def single_mode(output_dir: Path, state: State, desc: Optional[str] = None):
    """Single generation mode"""
    generate_and_run(output_dir, state, 1, user_desc=desc)

# ============================================================================
# INITIALIZATION
# ============================================================================

def init_check():
    """Verify environment and dependencies"""
    header("Initialization")
    
    # Check Python modules
    try:
        from cd5220 import CD5220, DiffAnimator
        ok("cd5220 module OK")
    except ImportError as e:
        err(f"cd5220 import failed: {e}")
        err("Run: pip3 install -r ~/cd5220/requirements.txt")
        sys.exit(1)
    
    # Check device
    device_path = Path(VFD_DEVICE)
    if not device_path.exists():
        err(f"Device not found: {VFD_DEVICE}")
        err("Check USB connection and run detect_ftdi_vfd.sh")
        sys.exit(1)
    
    if not (os.access(device_path, os.R_OK) and os.access(device_path, os.W_OK)):
        err(f"No permission: {VFD_DEVICE}")
        err("Fix: sudo usermod -a -G dialout $USER && logout")
        sys.exit(1)
    
    ok(f"Device OK: {VFD_DEVICE}")
    
    # Check Ollama
    try:
        resp = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=5)
        resp.raise_for_status()
        
        models = resp.json().get('models', [])
        model_names = [m['name'] for m in models]
        
        if MODEL not in model_names:
            err(f"Model not found: {MODEL}")
            err(f"Available: {', '.join(model_names[:5])}")
            err(f"Fix: ollama pull {MODEL}")
            sys.exit(1)
        
        ok(f"Ready: {MODEL}")
    except Exception as e:
        err(f"Ollama error: {e}")
        err(f"Ensure Ollama is running at {OLLAMA_API_BASE}")
        sys.exit(1)
    
    info(f"Config: {MIN_INTERVAL}s min interval, {ANIMATION_DURATION}s duration, {MAX_RETRIES} retries")

# ============================================================================
# MAIN
# ============================================================================

def main():
    global VERBOSE, MIN_INTERVAL, ANIMATION_DURATION, MAX_RETRIES
    
    parser = argparse.ArgumentParser(
        description='VFD Animation Agent - Autonomous AI Art Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Run continuous mode
  %(prog)s -v -i 60                     # Verbose, 60s min interval
  %(prog)s -s "bouncing ball"           # Single generation
  OLLAMA_MODEL=gemma2:2b %(prog)s       # Use different model

Environment Variables:
  VFD_DEVICE          Serial device (default: /dev/ttyUSB0)
  OLLAMA_API_BASE     Ollama endpoint (default: http://localhost:11434)
  OLLAMA_MODEL        Model name (default: qwen2.5:3b)
  MIN_INTERVAL        Min seconds between generations (default: 15)
  ANIMATION_DURATION  Animation length in seconds (default: 10.0)
        """
    )
    parser.add_argument('-s', '--single', metavar='DESC', help='Single generation mode')
    parser.add_argument('-i', '--interval', type=int, metavar='SEC', help='Minimum interval (seconds)')
    parser.add_argument('-d', '--duration', type=float, metavar='SEC', help='Animation duration (seconds)')
    parser.add_argument('-r', '--retries', type=int, metavar='NUM', help='Max retry attempts (default: 3)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose debug output')
    parser.add_argument('--version', action='version', version='VFD Animation Agent v1.0')
    
    args = parser.parse_args()
    
    VERBOSE = args.verbose
    if args.interval: MIN_INTERVAL = args.interval
    if args.duration: ANIMATION_DURATION = args.duration
    if args.retries: MAX_RETRIES = args.retries
    
    # Setup directories
    script_dir = Path(__file__).parent
    output_dir = script_dir / 'generated_animations'
    output_dir.mkdir(exist_ok=True)
    
    state = State(output_dir / 'agent_state.json')
    
    # Initialize and run
    init_check()
    
    try:
        if args.single:
            single_mode(output_dir, state, args.single)
        else:
            continuous_mode(output_dir, state)
    except KeyboardInterrupt:
        info("\nStopped gracefully")
        sys.exit(0)

if __name__ == '__main__':
    main()
