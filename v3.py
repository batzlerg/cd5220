#!/usr/bin/env python3
"""
VFD Animation Agent - Production AI Art Display
Research-driven continuous generation with full-screen enforcement
v3.0.0
"""

import sys
import os
import json
import random
import time
import argparse
import threading
import queue
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Tuple, Callable, List
from datetime import datetime
import requests

# Import from local CD5220 directory
from cd5220 import CD5220, DiffAnimator

# ============================================================================
# CONFIGURATION
# ============================================================================

VFD_DEVICE = os.getenv('VFD_DEVICE', '/dev/ttyUSB0')
VFD_BAUDRATE = 9600
OLLAMA_API_BASE = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')
ANIMATION_DURATION = float(os.getenv('ANIMATION_DURATION', '10.0'))
FRAME_RATE = 6
MAX_RETRIES = 5
QUEUE_SIZE = 2
GENERATION_TIMEOUT = 120

# Suppress library debug logs
logging.getLogger('CD5220').setLevel(logging.WARNING)

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

def info(msg: str): print(f"{C.INFO}ℹ{C.RESET} {msg}", file=sys.stderr, flush=True)
def ok(msg: str): print(f"{C.OK}✓{C.RESET} {msg}", file=sys.stderr, flush=True)
def err(msg: str): print(f"{C.ERR}✗{C.RESET} {msg}", file=sys.stderr, flush=True)
def warn(msg: str): print(f"{C.WARN}⚠{C.RESET} {msg}", file=sys.stderr, flush=True)
def debug(msg: str):
    if VERBOSE:
        print(f"{C.DEBUG}[DEBUG]{C.RESET} {msg}", file=sys.stderr, flush=True)

def header(msg: str):
    print(f"\n{C.BOLD}{'='*50}{C.RESET}", file=sys.stderr, flush=True)
    print(f"{C.BOLD}{msg}{C.RESET}", file=sys.stderr, flush=True)
    print(f"{C.BOLD}{'='*50}{C.RESET}", file=sys.stderr, flush=True)

# ============================================================================
# ENHANCED SYSTEM PROMPT
# ============================================================================

PROMPT = """Create FULL-SCREEN animated function for 20x2 VFD. Both rows MUST show motion!

CRITICAL RULES:
1. def FUNCNAME(animator: DiffAnimator, duration: float = 10.0)
2. animator.write_frame(line1_20char, line2_20char) - call every frame
3. animator.frame_sleep(1.0/animator.frame_rate)
4. text[:20].ljust(20) for exact 20 chars
5. frame_count = int(duration * animator.frame_rate)
6. Use 'frame' variable to create MOTION
7. Libraries: random, math
8. BOTH line1 AND line2 must have content/motion - NOT just one row!
9. Use FULL WIDTH (14+ of 20 columns active)

CHARACTER FAMILIES (use variety!):
- Rotational: | / - \\ < ^ > v
- Density: . o O @ * # % +
- Organic: . o O * ~ -
- Structural: [ ] ( ) { } = _

SPATIAL PATTERNS:
- CROSS-ROW: Track (x,y) where y in {0,1}, entities move between rows
- CASCADE: Spawn at row 0, move to row 1, cycle through
- WAVE: Offset between rows (row2_phase = row1_phase + 3)
- MIRROR: Symmetric or complementary patterns across rows
- INDEPENDENT: Different animations per row that coordinate

EXAMPLES:

def cross_row_bounce(animator: DiffAnimator, duration: float = 10.0):
    ballx, bally = 0, 0
    velx, vely = 1, 1
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        ballx += velx
        bally += vely
        if ballx <= 0 or ballx >= 19:
            velx = -velx
        if bally < 0 or bally > 1:
            vely = -vely
        bally = max(0, min(1, bally))
        line1 = [' '] * 20
        line2 = [' '] * 20
        if bally == 0:
            line1[ballx] = 'O'
        else:
            line2[ballx] = 'O'
        animator.write_frame(''.join(line1), ''.join(line2))
        animator.frame_sleep(1.0 / animator.frame_rate)

def cascade_rain(animator: DiffAnimator, duration: float = 10.0):
    drops = {}
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        if random.random() < 0.3:
            x = random.randint(0, 19)
            drops[x] = 0
        line1 = [' '] * 20
        line2 = [' '] * 20
        to_remove = []
        for x, y in list(drops.items()):
            if y == 0:
                line1[x] = '|'
                drops[x] = 1
            elif y == 1:
                line2[x] = '|'
                to_remove.append(x)
        for x in to_remove:
            del drops[x]
        animator.write_frame(''.join(line1), ''.join(line2))
        animator.frame_sleep(1.0 / animator.frame_rate)

def wave_sync(animator: DiffAnimator, duration: float = 10.0):
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        line1 = [' '] * 20
        line2 = [' '] * 20
        for x in range(20):
            phase1 = (frame + x) % 8
            phase2 = (frame + x + 3) % 8
            if phase1 < 2:
                line1[x] = '.'
            elif phase1 < 4:
                line1[x] = 'o'
            elif phase1 < 6:
                line1[x] = 'O'
            else:
                line1[x] = 'o'
            if phase2 < 2:
                line2[x] = '.'
            elif phase2 < 4:
                line2[x] = 'o'
            elif phase2 < 6:
                line2[x] = 'O'
            else:
                line2[x] = 'o'
        animator.write_frame(''.join(line1), ''.join(line2))
        animator.frame_sleep(1.0 / animator.frame_rate)

OUTPUT ONLY CODE. NO MARKDOWN."""

# ============================================================================
# STATE & STATS
# ============================================================================

class State:
    def __init__(self, state_file: Path):
        self.file = state_file
        self.data = self._load()
        self.lock = threading.Lock()
    
    def _load(self) -> Dict:
        if self.file.exists():
            try:
                with open(self.file) as f:
                    return json.load(f)
            except:
                return {'generations': [], 'success': 0, 'failure': 0}
        return {'generations': [], 'success': 0, 'failure': 0}
    
    def save(self, func: str, desc: str, status: str, error: str = ""):
        with self.lock:
            self.data['generations'].append({
                'timestamp': int(time.time()),
                'function': func,
                'description': desc,
                'status': status,
                'error': error[:200] if error else ""
            })
            self.data[status] = self.data.get(status, 0) + 1
            self.data['generations'] = self.data['generations'][-100:]
            
            try:
                with open(self.file, 'w') as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                debug(f"State save failed: {e}")
    
    def stats(self) -> str:
        with self.lock:
            s = self.data.get('success', 0)
            f = self.data.get('failure', 0)
            return f"✓{s} ✗{f}"

# ============================================================================
# ENHANCED IDEA GENERATOR
# ============================================================================

def generate_idea() -> str:
    """Generate animation ideas emphasizing full-screen usage"""
    
    patterns = [
        'cascade', 'wave', 'bounce', 'drift', 'pulse', 'spin', 'sweep',
        'flow', 'ripple', 'orbit', 'scatter', 'converge', 'spiral'
    ]
    
    elements = [
        'rain', 'stars', 'dots', 'particles', 'waves', 'lines', 'symbols',
        'arrows', 'rings', 'trails', 'sparks', 'bubbles', 'snowflakes'
    ]
    
    modifiers = [
        'dual row', 'synchronized', 'mirrored', 'offset', 'alternating',
        'crossing', 'rising', 'falling', 'expanding', 'contracting'
    ]
    
    return f"{random.choice(modifiers)} {random.choice(patterns)} {random.choice(elements)}"

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_dual_row_usage(code: str) -> Tuple[bool, str]:
    """Check if animation uses both rows"""
    
    # Must have both line1 and line2 assignments
    has_line1 = 'line1' in code
    has_line2 = 'line2' in code
    
    if not (has_line1 and has_line2):
        return False, "Missing line1 or line2 variable"
    
    # Check for list initialization pattern
    line1_init = re.search(r'line1\s*=\s*\[', code)
    line2_init = re.search(r'line2\s*=\s*\[', code)
    
    if line1_init and line2_init:
        return True, ""
    
    # Alternative: string building
    line1_str = re.search(r'line1\s*=\s*["\']', code)
    line2_str = re.search(r'line2\s*=\s*["\']', code)
    
    if line1_str and line2_str:
        return True, ""
    
    return False, "Both rows not properly initialized"

def validate_width_usage(code: str) -> Tuple[bool, str]:
    """Check if animation uses reasonable width"""
    
    # Look for range(20) or similar patterns
    full_width_patterns = [
        r'range\(\s*20\s*\)',
        r'for\s+\w+\s+in\s+range\(20\)',
        r'\[\s*\' \'\s*\]\s*\*\s*20'
    ]
    
    for pattern in full_width_patterns:
        if re.search(pattern, code):
            return True, ""
    
    # Check for coordinate tracking
    if 'ballx' in code or 'x' in code:
        return True, ""
    
    return False, "No evidence of full-width usage"

def validate_motion(code: str) -> Tuple[bool, str]:
    """Check if animation has motion logic"""
    
    motion_indicators = [
        'frame',
        'velocity',
        'vel',
        'position',
        'pos',
        'movement',
        'move',
        'offset'
    ]
    
    for indicator in motion_indicators:
        if indicator in code.lower():
            return True, ""
    
    return False, "No motion logic detected"

def validate_character_variety(code: str) -> Tuple[bool, str]:
    """Check for character family usage"""
    
    # Count unique non-space display characters in string literals
    chars = set()
    for match in re.finditer(r'["\']([^"\']+)["\']', code):
        content = match.group(1)
        chars.update(c for c in content if c not in ' \n\t')
    
    if len(chars) >= 4:
        return True, ""
    
    return False, f"Only {len(chars)} unique characters (need 4+)"

# ============================================================================
# CODE GENERATION
# ============================================================================

def clean_code(raw_code: str, func_name: str) -> Tuple[Optional[str], str]:
    """Clean LLM output and validate structure - NO BACKTICKS IN STRINGS"""
    
    code = raw_code
    # Remove markdown fences WITHOUT using backticks in the code
    code = code.replace('python', '')
    code = code.replace(chr(96)*3, '')  # Use chr(96) for backtick character
    code = code.strip()
    
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
                func_start = i
                break
    
    if func_start == -1:
        return None, "No function definition found"
    
    func_code = '\n'.join(lines[func_start:])
    
    # Basic API validation
    if 'write_frame' not in func_code:
        return None, "Missing write_frame call"
    if 'frame_sleep' not in func_code:
        return None, "Missing frame_sleep call"
    if len(func_code) < 150:
        return None, f"Code too short ({len(func_code)} chars)"
    
    # Quality validations
    valid, error = validate_dual_row_usage(func_code)
    if not valid:
        return None, f"Row usage: {error}"
    
    valid, error = validate_width_usage(func_code)
    if not valid:
        return None, f"Width usage: {error}"
    
    valid, error = validate_motion(func_code)
    if not valid:
        return None, f"Motion: {error}"
    
    valid, error = validate_character_variety(func_code)
    if not valid:
        return None, f"Character variety: {error}"
    
    full_code = f"from cd5220 import DiffAnimator\nimport random\nimport math\n\n{func_code}\n"
    
    return full_code, ""

def generate_code(desc: str, func_name: str, attempt: int, prev_errors: List[str]) -> Tuple[Optional[str], str]:
    """Generate code via Ollama with retry context"""
    
    debug(f"Generate attempt {attempt}/{MAX_RETRIES}: {desc}")
    
    retry_context = ""
    if attempt > 1:
        error_summary = "\n".join(f"- {err}" for err in prev_errors[-3:])
        retry_context = f"\n\nPREVIOUS ATTEMPTS FAILED:\n{error_summary}\n\nFIX: Ensure BOTH rows active, FULL width, MOTION with frame variable, 4+ unique chars."
    
    user_prompt = f"Create: {desc}\nFunction name: {func_name}{retry_context}\n\nOutput ONLY function code."
    full_prompt = f"{PROMPT}\n\n{user_prompt}"
    
    payload = {
        'model': MODEL,
        'prompt': full_prompt,
        'stream': False,
        'options': {
            'temperature': max(0.4, 0.8 - (attempt * 0.08)),
            'num_predict': 800,
            'stop': ['\n\ndef ', '\nif __name__', '\nExample:']
        }
    }
    
    try:
        resp = requests.post(
            f"{OLLAMA_API_BASE}/api/generate",
            json=payload,
            timeout=GENERATION_TIMEOUT
        )
        resp.raise_for_status()
        
        data = resp.json()
        raw_code = data.get('response', '')
        
        if not raw_code:
            return None, "Empty API response"
        
        return clean_code(raw_code, func_name)
        
    except requests.exceptions.Timeout:
        return None, f"API timeout after {GENERATION_TIMEOUT}s"
    except requests.exceptions.RequestException as e:
        return None, f"API error: {str(e)[:100]}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)[:100]}"

def validate_syntax(code: str) -> Tuple[bool, str]:
    """Validate Python syntax"""
    try:
        compile(code, '<string>', 'exec')
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

# ============================================================================
# ANIMATION PACKAGE
# ============================================================================

class Animation:
    """Self-contained animation with metadata"""
    def __init__(self, func_name: str, desc: str, code: str, callable_func: Callable):
        self.func_name = func_name
        self.desc = desc
        self.code = code
        self.callable = callable_func
        self.created_at = time.time()
    
    def run(self, animator: DiffAnimator, duration: float):
        """Execute animation safely"""
        try:
            self.callable(animator, duration=duration)
        except Exception as e:
            debug(f"Animation runtime error: {e}")
            raise

# ============================================================================
# BACKGROUND GENERATOR
# ============================================================================

class Generator:
    """Background generation thread with quality enforcement"""
    
    def __init__(self, animation_queue: queue.Queue, state: State, output_dir: Path):
        self.queue = animation_queue
        self.state = state
        self.output_dir = output_dir
        self.running = False
        self.thread = None
        self.gen_count = 0
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._generate_loop, daemon=True)
        self.thread.start()
        debug("Generator thread started")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        info("Generator stopped")
    
    def _generate_loop(self):
        while self.running:
            try:
                if self.queue.qsize() < QUEUE_SIZE:
                    self._generate_one()
                else:
                    time.sleep(1)
            except Exception as e:
                err(f"Generator error: {e}")
                time.sleep(5)
    
    def _generate_one(self):
        self.gen_count += 1
        
        desc = generate_idea()
        func_name = f"anim_{int(time.time())}_{random.randint(1000,9999)}"
        code_file = self.output_dir / f"{func_name}.py"
        
        debug(f"Gen #{self.gen_count}: {desc}")
        
        all_errors = []
        
        for attempt in range(1, MAX_RETRIES + 1):
            code, gen_error = generate_code(desc, func_name, attempt, all_errors)
            
            if not code:
                all_errors.append(f"Gen{attempt}: {gen_error}")
                continue
            
            # Save code
            try:
                code_file.write_text(code)
            except Exception as e:
                all_errors.append(f"Save{attempt}: {e}")
                continue
            
            # Syntax check
            valid, syntax_error = validate_syntax(code)
            if not valid:
                all_errors.append(f"Syntax{attempt}: {syntax_error}")
                continue
            
            # Compile to callable
            try:
                namespace = {
                    'DiffAnimator': DiffAnimator,
                    'random': random,
                    'math': __import__('math')
                }
                exec(code, namespace)
                
                if func_name not in namespace:
                    all_errors.append(f"Exec{attempt}: Function not in namespace")
                    continue
                
                animation = Animation(func_name, desc, code, namespace[func_name])
                
                self.queue.put(animation)
                self.state.save(func_name, desc, 'success')
                ok(f"✓ Generated: {desc}")
                return
                
            except Exception as e:
                all_errors.append(f"Compile{attempt}: {str(e)[:100]}")
                continue
        
        # All attempts failed
        final_error = " | ".join(all_errors[-3:])
        self.state.save(func_name, desc, 'failure', final_error)
        warn(f"✗ Failed after {MAX_RETRIES} attempts: {desc}")

# ============================================================================
# DISPLAY CONTROLLER
# ============================================================================

class DisplayController:
    """Main display loop with fault tolerance"""
    
    def __init__(self, animation_queue: queue.Queue, state: State):
        self.queue = animation_queue
        self.state = state
        self.display = None
        self.animator = None
        self.running = False
        self.play_count = 0
    
    def start(self):
        """Initialize display hardware"""
        try:
            self.display = CD5220(VFD_DEVICE, baudrate=VFD_BAUDRATE)
            self.animator = DiffAnimator(self.display, frame_rate=FRAME_RATE, render_console=False)
            self.animator.clear_display()
            ok(f"Display ready: {VFD_DEVICE} @ {FRAME_RATE}fps")
        except Exception as e:
            err(f"Display init failed: {e}")
            raise
    
    def run(self):
        """Main display loop"""
        self.running = True
        
        while self.running:
            try:
                try:
                    animation = self.queue.get(timeout=20)
                except queue.Empty:
                    warn("Queue empty - showing placeholder")
                    self._show_placeholder()
                    continue
                
                # Play animation
                self.play_count += 1
                queue_depth = self.queue.qsize()
                info(f"▶ #{self.play_count}: {animation.desc[:40]} | Q:{queue_depth} | {self.state.stats()}")
                
                try:
                    animation.run(self.animator, ANIMATION_DURATION)
                except Exception as e:
                    err(f"Playback error: {e}")
                finally:
                    self.animator.clear_display()
                    time.sleep(0.2)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                err(f"Display loop error: {e}")
                time.sleep(1)
    
    def _show_placeholder(self):
        """Generating placeholder with animation"""
        try:
            for i in range(60):
                if not self.queue.empty():
                    break
                
                dots = "." * (i % 4)
                spinner = ['|', '/', '-', '\\'][i % 4]
                
                line1 = f"  GENERATING{dots}".ljust(20)
                line2 = f"   Please wait {spinner}   ".ljust(20)
                
                self.animator.write_frame(line1, line2)
                time.sleep(0.5)
            
            self.animator.clear_display()
        except Exception as e:
            debug(f"Placeholder error: {e}")
    
    def stop(self):
        self.running = False
        if self.animator:
            try:
                self.animator.clear_display()
            except:
                pass

# ============================================================================
# INITIALIZATION
# ============================================================================

def init_check():
    """Verify environment and dependencies"""
    header("System Check")
    
    # Check Python modules
    try:
        from cd5220 import CD5220, DiffAnimator
        ok("cd5220 module imported")
    except ImportError as e:
        err(f"cd5220 import failed: {e}")
        err("Fix: Ensure you're in the CD5220 directory")
        sys.exit(1)
    
    # Check device
    device_path = Path(VFD_DEVICE)
    if not device_path.exists():
        err(f"Device not found: {VFD_DEVICE}")
        err("Fix: Check USB connection and device path")
        sys.exit(1)
    
    if not (os.access(device_path, os.R_OK) and os.access(device_path, os.W_OK)):
        err(f"Permission denied: {VFD_DEVICE}")
        err("Fix: sudo usermod -a -G dialout $USER && logout")
        sys.exit(1)
    
    ok(f"Device accessible: {VFD_DEVICE}")
    
    # Check Ollama
    try:
        resp = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=5)
        resp.raise_for_status()
        
        models = resp.json().get('models', [])
        model_names = [m['name'] for m in models]
        
        if MODEL not in model_names:
            err(f"Model not found: {MODEL}")
            err(f"Fix: ollama pull {MODEL}")
            sys.exit(1)
        
        ok(f"Model ready: {MODEL}")
    except requests.exceptions.ConnectionError:
        err("Cannot connect to Ollama")
        err("Fix: Ensure Ollama is running (ollama serve)")
        sys.exit(1)
    except Exception as e:
        err(f"Ollama check failed: {e}")
        sys.exit(1)
    
    info(f"Config: {ANIMATION_DURATION}s animations @ {FRAME_RATE}fps")

# ============================================================================
# MAIN
# ============================================================================

def main():
    global VERBOSE, ANIMATION_DURATION
    
    parser = argparse.ArgumentParser(
        description='VFD Animation Agent v3.0 - Full-Screen AI Art Display',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Production animation generator with quality enforcement.
Generates full-screen dual-row animations continuously.

Examples:
  %(prog)s                    # Run with defaults
  %(prog)s -v                 # Verbose debug mode
  %(prog)s -d 15              # 15s animations
  %(prog)s --fps 8            # 8 FPS playback

Environment:
  VFD_DEVICE          Serial device (default: /dev/ttyUSB0)
  OLLAMA_API_BASE     Ollama endpoint (default: http://localhost:11434)
  OLLAMA_MODEL        Model name (default: qwen2.5:3b)
  ANIMATION_DURATION  Animation length (default: 10.0)
        """
    )
    parser.add_argument('-d', '--duration', type=float, metavar='SEC', help='Animation duration')
    parser.add_argument('-f', '--fps', type=int, metavar='FPS', help='Frame rate')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose debug output')
    parser.add_argument('--version', action='version', version='VFD Agent v3.0')
    
    args = parser.parse_args()
    
    global FRAME_RATE
    VERBOSE = args.verbose
    if args.duration:
        ANIMATION_DURATION = args.duration
    if args.fps:
        FRAME_RATE = args.fps
    
    # Setup directories
    script_dir = Path(__file__).parent
    output_dir = script_dir / 'generated_animations'
    output_dir.mkdir(exist_ok=True)
    
    state = State(output_dir / 'agent_state.json')
    animation_queue = queue.Queue(maxsize=QUEUE_SIZE)
    
    # Initialize
    init_check()
    
    # Start components
    header("Starting Continuous Display")
    info("Full-screen dual-row animations enforced")
    info("Quality validation: row usage, width, motion, character variety")
    info("Press Ctrl+C to stop")
    
    generator = Generator(animation_queue, state, output_dir)
    display = DisplayController(animation_queue, state)
    
    try:
        # Pre-generate
        info("Pre-generating initial animations...")
        generator.start()
        
        # Wait for queue
        wait_start = time.time()
        while animation_queue.qsize() < QUEUE_SIZE:
            if time.time() - wait_start > 60:
                warn("Initial generation taking longer than expected...")
                wait_start = time.time()
            time.sleep(0.5)
        
        ok(f"Queue ready ({animation_queue.qsize()} animations)")
        
        # Start display
        display.start()
        display.run()
        
    except KeyboardInterrupt:
        info("\nShutting down gracefully...")
    except Exception as e:
        err(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        generator.stop()
        display.stop()
        info("Agent stopped")

if __name__ == '__main__':
    main()
