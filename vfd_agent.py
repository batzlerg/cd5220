#!/usr/bin/env python3
"""
VFD Animation Agent - Continuous AI Art Display
Zero-downtime generative art with background generation pipeline
v2.0.5
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
from pathlib import Path
from typing import Optional, Dict, Tuple, Callable
from datetime import datetime
import requests

sys.path.insert(0, str(Path.home() / 'cd5220'))
from cd5220 import CD5220, DiffAnimator

# ============================================================================
# CONFIGURATION
# ============================================================================

VFD_DEVICE = os.getenv('VFD_DEVICE', '/dev/ttyUSB0')
VFD_BAUDRATE = 9600
OLLAMA_API_BASE = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')
ANIMATION_DURATION = float(os.getenv('ANIMATION_DURATION', '10.0'))
BUFFER_TIME = float(os.getenv('BUFFER_TIME', '5.0'))
FRAME_RATE = 6
MAX_RETRIES = 3
QUEUE_SIZE = 2
GENERATION_TIMEOUT = 120

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Suppress cd5220 library's verbose DEBUG logs
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
    print(f"\n{C.BOLD}{'='*40}{C.RESET}", file=sys.stderr, flush=True)
    print(f"{C.BOLD}{msg}{C.RESET}", file=sys.stderr, flush=True)
    print(f"{C.BOLD}{'='*40}{C.RESET}", file=sys.stderr, flush=True)

# ============================================================================
# SYSTEM PROMPT
# ============================================================================

PROMPT = """Create ANIMATED function for 20x2 VFD. MOTION required!

RULES:
1. def FUNCNAME(animator: DiffAnimator, duration: float = 10.0)
2. animator.write_frame(line1_20char, line2_20char)
3. animator.frame_sleep(1.0/animator.frame_rate)
4. text[:20].ljust(20)
5. frame_count = int(duration * animator.frame_rate)
6. Use 'frame' for MOTION
7. random, math available
8. Output ONLY code - NO markdown

EXAMPLES:

def scroll_text(animator: DiffAnimator, duration: float = 10.0):
    text = "HELLO WORLD  "
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        offset = frame % len(text)
        line1 = (text[offset:] + text)[:20].ljust(20)
        animator.write_frame(line1, " " * 20)
        animator.frame_sleep(1.0 / animator.frame_rate)

def bounce_ball(animator: DiffAnimator, duration: float = 10.0):
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        pos = int(abs(10 * math.sin(frame * 0.3)))
        line1 = (" " * pos + "O" + " " * (19-pos))[:20].ljust(20)
        animator.write_frame(line1, " " * 20)
        animator.frame_sleep(1.0 / animator.frame_rate)

OUTPUT ONLY CODE."""

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
            self.data['generations'] = self.data['generations'][-50:]
            
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
# IDEA GENERATOR
# ============================================================================

def generate_idea() -> str:
    patterns = ['scroll', 'pulse', 'bounce', 'fade', 'wave', 'blink', 'sweep', 'spin']
    elements = ['text', 'dots', 'stars', 'lines', 'bars', 'arrow', 'box', 'waves']
    styles = ['simple', 'smooth', 'fast', 'slow', 'random', 'steady']
    return f"{random.choice(patterns)} {random.choice(elements)} {random.choice(styles)}"

# ============================================================================
# CODE GENERATION
# ============================================================================

def clean_code(raw_code: str, func_name: str) -> Tuple[Optional[str], str]:
    """Clean LLM output"""
    
    code = raw_code
    code = code.replace('`'*3 + 'python', '')
    code = code.replace('`'*3, '')
    code = code.strip()
    
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
    full_code = f"from cd5220 import DiffAnimator\n\n{func_code}\n"
    
    if 'write_frame' not in full_code:
        return None, "Missing write_frame"
    if 'frame_sleep' not in full_code:
        return None, "Missing frame_sleep"
    if len(full_code) < 100:
        return None, f"Code too short ({len(full_code)} chars)"
    
    return full_code, ""

def generate_code(desc: str, func_name: str, attempt: int, prev_errors: str) -> Tuple[Optional[str], str]:
    """Generate code via Ollama"""
    
    debug(f"Generate attempt {attempt}: {desc}")
    
    retry_context = ""
    if attempt > 1:
        retry_context = f"\nPREVIOUS FAILED:\n{prev_errors}\n\nFIX: Output ONLY code."
    
    user_prompt = f"Create: {desc}\nName: {func_name}{retry_context}\n\nOutput ONLY function code."
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
        resp = requests.post(
            f"{OLLAMA_API_BASE}/api/generate",
            json=payload,
            timeout=GENERATION_TIMEOUT
        )
        resp.raise_for_status()
        
        data = resp.json()
        raw_code = data.get('response', '')
        
        if not raw_code:
            return None, "Empty response"
        
        return clean_code(raw_code, func_name)
        
    except Exception as e:
        return None, f"API error: {str(e)[:100]}"

def validate_syntax(code: str) -> Tuple[bool, str]:
    """Validate syntax"""
    try:
        compile(code, '<string>', 'exec')
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"

# ============================================================================
# ANIMATION PACKAGE
# ============================================================================

class Animation:
    """Self-contained animation package"""
    def __init__(self, func_name: str, desc: str, code: str, callable_func: Callable):
        self.func_name = func_name
        self.desc = desc
        self.code = code
        self.callable = callable_func
        self.created_at = time.time()
    
    def run(self, animator: DiffAnimator, duration: float):
        """Execute animation"""
        self.callable(animator, duration=duration)

# ============================================================================
# BACKGROUND GENERATOR
# ============================================================================

class Generator:
    """Background generation thread"""
    
    def __init__(self, animation_queue: queue.Queue, state: State, output_dir: Path):
        self.queue = animation_queue
        self.state = state
        self.output_dir = output_dir
        self.running = False
        self.thread = None
        self.gen_count = 0
    
    def start(self):
        """Start background thread"""
        self.running = True
        self.thread = threading.Thread(target=self._generate_loop, daemon=True)
        self.thread.start()
        debug("Generator thread started")
    
    def stop(self):
        """Stop background thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        info("Generator thread stopped")
    
    def _generate_loop(self):
        """Main generation loop"""
        while self.running:
            try:
                if self.queue.qsize() < QUEUE_SIZE:
                    self._generate_one()
                else:
                    time.sleep(1)
            except Exception as e:
                debug(f"Generator error: {e}")
                time.sleep(5)
    
    def _generate_one(self):
        """Generate single animation"""
        self.gen_count += 1
        
        desc = generate_idea()
        func_name = f"anim_{int(time.time())}_{random.randint(1000,9999)}"
        code_file = self.output_dir / f"{func_name}.py"
        
        debug(f"Gen #{self.gen_count}: {desc}")
        
        all_errors = []
        
        for attempt in range(1, MAX_RETRIES + 1):
            prev_errors = "\n".join(all_errors[-2:]) if all_errors else ""
            
            code, gen_error = generate_code(desc, func_name, attempt, prev_errors)
            
            if not code:
                all_errors.append(f"Gen: {gen_error}")
                continue
            
            try:
                code_file.write_text(code)
            except Exception as e:
                all_errors.append(f"Save: {e}")
                continue
            
            valid, syntax_error = validate_syntax(code)
            if not valid:
                all_errors.append(f"Syntax: {syntax_error}")
                continue
            
            # Compile to callable
            try:
                import random as rand_mod
                import math
                namespace = {
                    'DiffAnimator': DiffAnimator,
                    'random': rand_mod,
                    'math': math
                }
                exec(code, namespace)
                
                if func_name not in namespace:
                    all_errors.append("Function not in namespace")
                    continue
                
                animation = Animation(func_name, desc, code, namespace[func_name])
                
                self.queue.put(animation)
                self.state.save(func_name, desc, 'success')
                debug(f"✓ Queued: {desc}")
                return
                
            except Exception as e:
                all_errors.append(f"Compile: {str(e)}")
                continue
        
        # All attempts failed
        final_error = " | ".join(all_errors[-3:])
        self.state.save(func_name, desc, 'failure', final_error)
        debug(f"✗ Failed: {desc}")

# ============================================================================
# DISPLAY CONTROLLER
# ============================================================================

class DisplayController:
    """Main display thread"""
    
    def __init__(self, animation_queue: queue.Queue, state: State):
        self.queue = animation_queue
        self.state = state
        self.display = None
        self.animator = None
        self.running = False
        self.play_count = 0
    
    def start(self):
        """Initialize display"""
        try:
            self.display = CD5220(VFD_DEVICE, baudrate=VFD_BAUDRATE)
            self.animator = DiffAnimator(self.display, frame_rate=FRAME_RATE, render_console=False)
            ok(f"Display connected: {VFD_DEVICE}")
        except Exception as e:
            err(f"Display init failed: {e}")
            raise
    
    def run(self):
        """Main display loop"""
        self.running = True
        
        while self.running:
            try:
                # Get next animation (block with timeout)
                try:
                    animation = self.queue.get(timeout=15)
                except queue.Empty:
                    self._show_placeholder()
                    continue
                
                # Play animation
                self.play_count += 1
                queue_depth = self.queue.qsize()
                info(f"▶ #{self.play_count}: {animation.desc} | Queue: {queue_depth} | {self.state.stats()}")
                
                try:
                    animation.run(self.animator, ANIMATION_DURATION)
                    self.animator.clear_display()
                except Exception as e:
                    err(f"Playback error: {e}")
                    self.animator.clear_display()
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                err(f"Display error: {e}")
                time.sleep(1)
    
    def _show_placeholder(self):
        """Show 'generating' placeholder"""
        warn("Queue empty - showing placeholder")
        
        try:
            for i in range(30):
                if not self.queue.empty():
                    break
                dots = "." * ((i % 4))
                line1 = f"GENERATING{dots}".ljust(20)
                self.animator.write_frame(line1, " " * 20)
                time.sleep(0.5)
            self.animator.clear_display()
        except:
            pass
    
    def stop(self):
        """Cleanup"""
        self.running = False
        if self.animator:
            self.animator.clear_display()

# ============================================================================
# INITIALIZATION
# ============================================================================

def init_check():
    """Verify environment"""
    header("Initialization")
    
    # Check Python modules
    try:
        from cd5220 import CD5220, DiffAnimator
        ok("cd5220 module OK")
    except ImportError as e:
        err(f"cd5220 import failed: {e}")
        sys.exit(1)
    
    # Check device
    device_path = Path(VFD_DEVICE)
    if not device_path.exists():
        err(f"Device not found: {VFD_DEVICE}")
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
            err(f"Fix: ollama pull {MODEL}")
            sys.exit(1)
        
        ok(f"Model ready: {MODEL}")
    except Exception as e:
        err(f"Ollama error: {e}")
        sys.exit(1)
    
    info(f"Config: {ANIMATION_DURATION}s animations, {BUFFER_TIME}s buffer, queue size {QUEUE_SIZE}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    global VERBOSE, ANIMATION_DURATION, BUFFER_TIME
    
    parser = argparse.ArgumentParser(
        description='VFD Animation Agent - Continuous AI Art Display',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Zero-downtime generative art with background generation pipeline.
Animations generate in background while current animation plays.

Examples:
  %(prog)s                    # Run with defaults
  %(prog)s -v                 # Verbose mode
  %(prog)s -d 15              # 15s animations
  %(prog)s --buffer 3         # Start generating 3s before end

Environment:
  VFD_DEVICE          Serial device (default: /dev/ttyUSB0)
  OLLAMA_API_BASE     Ollama endpoint (default: http://localhost:11434)
  OLLAMA_MODEL        Model name (default: qwen2.5:3b)
  ANIMATION_DURATION  Animation length (default: 10.0)
  BUFFER_TIME         Pre-generate buffer (default: 5.0)
        """
    )
    parser.add_argument('-d', '--duration', type=float, metavar='SEC', help='Animation duration')
    parser.add_argument('-b', '--buffer', type=float, metavar='SEC', help='Generation buffer time')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose debug')
    parser.add_argument('--version', action='version', version='VFD Agent v2.0')
    
    args = parser.parse_args()
    
    VERBOSE = args.verbose
    if args.duration: ANIMATION_DURATION = args.duration
    if args.buffer: BUFFER_TIME = args.buffer
    
    # Setup
    script_dir = Path(__file__).parent
    output_dir = script_dir / 'generated_animations'
    output_dir.mkdir(exist_ok=True)
    
    state = State(output_dir / 'agent_state.json')
    animation_queue = queue.Queue(maxsize=QUEUE_SIZE)
    
    # Initialize
    init_check()
    
    # Start threads
    header("Starting Continuous Display")
    info("Display will NEVER be blank")
    info("Animations generate in background")
    info("Press Ctrl+C to stop")
    
    generator = Generator(animation_queue, state, output_dir)
    display = DisplayController(animation_queue, state)
    
    try:
        # Pre-generate initial animations
        info("Pre-generating initial animations...")
        generator.start()
        
        # Wait for queue to fill
        while animation_queue.qsize() < QUEUE_SIZE:
            time.sleep(0.5)
        
        ok(f"Queue filled ({animation_queue.qsize()} ready)")
        
        # Start display
        display.start()
        display.run()
        
    except KeyboardInterrupt:
        info("\nStopping gracefully...")
    except Exception as e:
        err(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        generator.stop()
        display.stop()
        info("Stopped")

if __name__ == '__main__':
    main()
