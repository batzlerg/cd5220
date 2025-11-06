#!/usr/bin/env python3
"""
VFD Animation Agent - AI-Driven VFD Art Display
Production-ready continuous animation generation with telemetry
Version: 4.16.0 - Added frame capture system
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
import termios
import tty
import select
from pathlib import Path
from typing import Optional, Dict, Tuple, Callable, List
from datetime import datetime
import requests

from cd5220 import CD5220, DiffAnimator
from telemetry_lite import VFDTelemetry
from code_metrics import analyze_code
from idea_generator import generate_idea
from frame_capture import FrameCapture, validate_frame_content  # ★ NEW IMPORT

# Configuration
VFD_DEVICE = os.getenv('VFD_DEVICE', '/dev/ttyUSB0')
VFD_BAUDRATE = 9600
OLLAMA_API_BASE = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:14b')
ANIMATION_DURATION = float(os.getenv('ANIMATION_DURATION', '10.0'))
FRAME_RATE = 6
MAX_RETRIES = 5
QUEUE_SIZE = 2
GENERATION_TIMEOUT = 120
DEFAULT_PROMPT_FILE = 'prompt.txt'
PREVIEW_MODE = False
CUSTOM_IDEA = None

# Logging
logging.getLogger('CD5220').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# Colors
class C:
    INFO = ''
    OK = ''
    ERR = ''
    WARN = ''
    DEBUG = ''
    BOLD = ''
    DIM = ''
    RESET = ''

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


class KeyboardListener:
    """Non-blocking keyboard listener for 'b' (bookmark) and 'd' (downvote) keys"""
    def __init__(self):
        self.bookmark_pressed = False
        self.downvote_pressed = False
        self.running = False
        self.thread = None
        self.old_settings = None

    def start(self):
        """Start listening for key presses in background thread"""
        if not sys.stdin.isatty():
            debug("Not a TTY, keyboard listener disabled")
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        debug("Keyboard listener started")

    def stop(self):
        """Stop the listener"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)

    def check_and_clear(self) -> bool:
        """Check if 'b' was pressed and clear the flag"""
        if self.bookmark_pressed:
            self.bookmark_pressed = False
            return True
        return False

    def check_and_clear_downvote(self) -> bool:
        """Check if 'd' was pressed and clear the flag"""
        if self.downvote_pressed:
            self.downvote_pressed = False
            return True
        return False

    def _listen(self):
        """Background thread that polls for 'b' and 'd' keys"""
        try:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            
            while self.running:
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    ch = sys.stdin.read(1).lower()
                    if ch == 'b':
                        self.bookmark_pressed = True
                        print(f"\n{C.OK}[★ Bookmark recorded!]{C.RESET}", file=sys.stderr, flush=True)
                    elif ch == 'd':
                        self.downvote_pressed = True
                        print(f"\n{C.ERR}[✗ Downvote recorded!]{C.RESET}", file=sys.stderr, flush=True)
        except Exception as e:
            debug(f"Keyboard listener error: {e}")
        finally:
            if self.old_settings:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                except:
                    pass


def load_prompt(prompt_file: Path) -> str:
    """Load the generation prompt from file"""
    try:
        with open(prompt_file, 'r') as f:
            prompt = f.read()
        ok(f"Loaded prompt: {prompt_file}")
        return prompt
    except FileNotFoundError:
        err(f"Prompt file not found: {prompt_file}")
        sys.exit(1)
    except Exception as e:
        err(f"Error loading prompt: {e}")
        sys.exit(1)


class State:
    """Thread-safe persistent state tracking"""
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
                return {"generations": [], "success": 0, "failure": 0}
        return {"generations": [], "success": 0, "failure": 0}

    def save(self, func: str, desc: str, status: str, error: str = ""):
        with self.lock:
            self.data["generations"].append({
                "timestamp": datetime.now().isoformat(),
                "function": func,
                "description": desc,
                "status": status,
                "error": error[:200] if error else ""
            })
            self.data[status] = self.data.get(status, 0) + 1
            self.data["generations"] = self.data["generations"][-100:]
            
            try:
                with open(self.file, 'w') as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                debug(f"State save failed: {e}")

    def stats(self) -> str:
        with self.lock:
            s = self.data.get("success", 0)
            f = self.data.get("failure", 0)
            return f"✓{s} ✗{f}"


class ProgressTracker:
    """Thread-safe progress tracking for loading animations"""
    def __init__(self, target: int):
        self.target = target
        self.current = 0.0
        self.lock = threading.Lock()

    def set_progress(self, value: float):
        with self.lock:
            self.current = min(value, self.target)

    def get_progress(self) -> Tuple[float, int]:
        with self.lock:
            return (self.current, self.target)


class DualAnimator:
    """Animator that outputs to both hardware and console (if preview enabled)"""
    def __init__(self, hardware_animator: DiffAnimator, preview_enabled: bool, capture_frames: bool = False):
        self.hardware = hardware_animator
        self.preview_enabled = preview_enabled
        self.frame_rate = hardware_animator.frame_rate
        
        # ★ NEW: Frame capture support
        self.frame_capture: Optional[FrameCapture] = None
        if capture_frames:
            self.frame_capture = FrameCapture(hardware_animator, animation_id="playback")

    def write_frame(self, line1: str, line2: str):
        self.hardware.write_frame(line1, line2)
        if self.preview_enabled:
            print(f"{'-'*20}", file=sys.stderr, flush=True)
            print(f"{line1}", file=sys.stderr, flush=True)
            print(f"{line2}", file=sys.stderr, flush=True)
            print(f"{'-'*20}", file=sys.stderr, flush=True)

    def frame_sleep(self, seconds: float):
        self.hardware.frame_sleep(seconds)

    def clear_display(self):
        self.hardware.clear_display()
    
    # ★ NEW: Access captured frames
    def get_frame_capture(self) -> Optional[FrameCapture]:
        return self.frame_capture


def validate_dual_row_usage(code: str) -> Tuple[bool, str]:
    has_line1 = 'line1' in code
    has_line2 = 'line2' in code
    if not (has_line1 and has_line2):
        return False, "Missing line1 or line2"
    return True, ""


def validate_width_usage(code: str) -> Tuple[bool, str]:
    patterns = [r'range\(20\)', r' 20']
    for p in patterns:
        if re.search(p, code):
            return True, ""
    if 'x in' in code.lower():
        return True, ""
    return False, "No full-width usage"


def validate_motion(code: str) -> Tuple[bool, str]:
    indicators = ['frame', 'velocity', 'vel', 'position', 'move', 'offset']
    for ind in indicators:
        if ind in code.lower():
            return True, ""
    return False, "No motion logic"


def validate_character_variety(code: str) -> Tuple[bool, str]:
    chars = set()
    for match in re.finditer(r"['\"](.*?)['\"]", code):
        chars.update(c for c in match.group(1) if c not in ' ')
    if len(chars) >= 4:
        return True, ""
    return False, f"Only {len(chars)} chars (need 4+)"


def clean_code(raw_code: str, func_name: str) -> Tuple[Optional[str], str]:
    """Extract and validate function code from LLM response"""
    code = raw_code.replace("``````", "").replace(chr(96)*3, "").strip()
    
    lines = code.split('\n')
    func_start = -1
    
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {func_name}"):
            func_start = i
            break
    
    if func_start == -1:
        for i, line in enumerate(lines):
            if 'def ' in line and 'animator' in line.lower():
                func_start = i
                break
    
    if func_start == -1:
        return None, "No function found"
    
    func_code = '\n'.join(lines[func_start:])
    
    if 'write_frame' not in func_code:
        return None, "Missing write_frame"
    if 'frame_sleep' not in func_code:
        return None, "Missing frame_sleep"
    if len(func_code) < 150:
        return None, f"Code too short"
    
    valid, error = validate_dual_row_usage(func_code)
    if not valid:
        return None, f"Row: {error}"
    
    valid, error = validate_motion(func_code)
    if not valid:
        return None, f"Motion: {error}"
    
    valid, error = validate_character_variety(func_code)
    if not valid:
        return None, f"Chars: {error}"
    
    full_code = f"from cd5220 import DiffAnimator\nimport random\nimport math\n\n{func_code}"
    return full_code, ""


def generate_code(prompt: str, desc: str, func_name: str, attempt: int, 
                 prev_errors: List[str], output_dir: Path,
                 progress: Optional[ProgressTracker] = None) -> Tuple[Optional[str], str, str]:
    """Generate animation code via Ollama API"""
    debug(f"Generate attempt {attempt}/{MAX_RETRIES}: {desc}")
    
    retry_context = ""
    if attempt > 1:
        error_summary = '\n'.join(f"- {err}" for err in prev_errors[-3:])
        retry_context = f"\n\nPREVIOUS ATTEMPT FAILED:\n{error_summary}\n\nFix the error above and generate corrected code."
    
    user_prompt = f"Create: {desc}\nFunction: {func_name}{retry_context}\n\nONLY output code."
    full_prompt = f"{prompt}\n\n{user_prompt}"
    
    if progress:
        progress.set_progress((attempt - 1))
    
    payload = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": max(0.6, 0.85 - (attempt * 0.05)),
            "num_predict": 2048,
            "stop": ["```\n"] 
        }
    }
    
    try:
        resp = requests.post(f"{OLLAMA_API_BASE}/api/generate", json=payload, timeout=GENERATION_TIMEOUT)
        resp.raise_for_status()
        
        raw_code = resp.json().get("response", "")
        if not raw_code:
            return None, "Empty response", ""
        
        code, error = clean_code(raw_code, func_name)
        
        if not code:
            failed_file = output_dir / f"failed_{func_name}_attempt{attempt}.txt"
            try:
                failed_file.write_text(f"Description: {desc}\n\n{'='*60}\nATTEMPT {attempt}\n{'='*60}\n\n{error}\n\n{'='*60}\nRESPONSE\n{'='*60}\n\n{raw_code}")
                debug(f"  ├─ Full response saved to {failed_file.relative_to(Path.cwd())}")
            except Exception as e:
                debug(f"  ├─ Could not save failed response: {e}")
            
            preview = raw_code[:200].replace('\n', ' ')
            debug(f"  ├─ Raw response preview: {preview}...")
        
        return code, error, raw_code
    except requests.exceptions.Timeout:
        return None, f"Timeout", ""
    except Exception as e:
        return None, f"Error: {str(e)[:100]}", ""


def validate_syntax(code: str) -> Tuple[bool, str]:
    """Validate Python syntax"""
    try:
        compile(code, '<string>', 'exec')
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def validate_runtime(func: Callable, func_name: str) -> Tuple[bool, str, Optional[FrameCapture]]:
    """
    Validate runtime behavior with fast test execution and frame capture.
    
    Returns:
        Tuple of (valid, error_message, frame_capture)
    """
    try:
        start_time = time.time()
        test_display = CD5220.create_simulator_only(debug=False, render_console=False)
        test_animator = DiffAnimator(
            test_display,
            frame_rate=600,
            frame_sleep_fn=lambda seconds: None,
            render_console=False
        )
        
        # ★ NEW: Wrap with frame capture
        capture = FrameCapture(test_animator, animation_id=func_name)
        
        # Run animation
        func(capture.animator, duration=1.0)
        
        elapsed = time.time() - start_time
        
        # ★ NEW: Validate frame content
        stats = capture.get_stats()
        valid, content_error = validate_frame_content(
            capture.get_frames(),
            empty_threshold=0.7,
            dual_row_threshold=0.2
        )
        
        if not valid:
            debug(f"  ├─ ✗ Frame validation failed: {content_error}")
            return False, content_error, None
        
        debug(f"  ├─ ✓ Runtime validation passed ({stats['total_frames']} frames, {stats['non_empty_frames']} non-empty, {elapsed:.2f}s)")
        return True, "", capture
        
    except IndexError as e:
        return False, f"IndexError: {str(e)[:100]}", None
    except Exception as e:
        return False, f"Runtime: {str(e)[:100]}", None


class Animation:
    """Container for generated animation code"""
    def __init__(self, func_name: str, desc: str, code: str, callable_func: Callable):
        self.func_name = func_name
        self.desc = desc
        self.code = code
        self.callable = callable_func
        self.created_at = time.time()

    def run(self, animator, duration: float):
        try:
            self.callable(animator, duration=duration)
        except Exception as e:
            debug(f"Animation error: {e}")
            raise


class Generator:
    """Background thread that generates animations and fills queue"""
    def __init__(self, animation_queue: queue.Queue, state: State, output_dir: Path, 
                 prompt: str, progress: Optional[ProgressTracker] = None):
        self.queue = animation_queue
        self.telemetry = VFDTelemetry(output_dir / "telemetry")
        self.state = state
        self.output_dir = output_dir
        self.prompt = prompt
        self.progress = progress
        self.running = False
        self.thread = None
        self.gen_count = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._generate_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            try:
                self.thread.join(timeout=2)
            except KeyboardInterrupt:
                pass
        info("Generator stopped")

    def _generate_loop(self):
        while self.running:
            try:
                if self.queue.qsize() < QUEUE_SIZE:
                    self.generate_one()
                else:
                    time.sleep(1)
            except Exception as e:
                err(f"Generator error: {e}")
                time.sleep(5)

    def generate_one(self):
        """Generate a single animation"""
        self.gen_count += 1
        desc = generate_idea()
        func_name = f"anim_{int(time.time())}_{random.randint(1000,9999)}"
        code_file = self.output_dir / f"{func_name}.py"
        
        progress_per_attempt = (1.0 / MAX_RETRIES) if self.progress else 0
        animation_start = (self.gen_count - 1) * 1.0
        
        all_errors = []
        
        for attempt in range(1, MAX_RETRIES + 1):
            if self.progress:
                self.progress.set_progress(animation_start + (attempt - 1) * progress_per_attempt)
            
            code, gen_error, raw_response = generate_code(
                self.prompt, desc, func_name, attempt, all_errors, self.output_dir
            )
            
            if not code:
                debug(f"  ├─ ✗ Code generation failed: {gen_error}")
                all_errors.append(f"Gen[{attempt}]: {gen_error}")
                continue
            
            debug(f"  ├─ ✓ Code received ({len(code)} chars)")
            
            try:
                code_file.write_text(code)
                debug(f"  ├─ ✓ Saved to {code_file.name}")
            except Exception as e:
                debug(f"  ├─ ✗ Save failed: {e}")
                all_errors.append(f"Save: {e}")
                continue
            
            valid, syntax_error = validate_syntax(code)
            if not valid:
                debug(f"  ├─ ✗ Syntax validation failed: {syntax_error}")
                all_errors.append(f"Syntax: {syntax_error}")
                continue
            
            debug(f"  ├─ ✓ Syntax valid")
            
            try:
                namespace = {'DiffAnimator': DiffAnimator, 'random': random, 'math': __import__('math')}
                exec(code, namespace)
                
                if func_name not in namespace:
                    debug(f"  ├─ ✗ Function not found in namespace")
                    all_errors.append("Function missing")
                    continue
                
                debug(f"  ├─ ✓ Compiled successfully")
                
                # ★ MODIFIED: Runtime validation now returns frame capture
                valid_runtime, runtime_error, frame_capture = validate_runtime(namespace[func_name], func_name)
                if not valid_runtime:
                    debug(f"  ├─ ✗ Runtime validation failed: {runtime_error}")
                    all_errors.append(f"Runtime: {runtime_error}")
                    continue
                
                # ★ NEW: Save captured frames
                if frame_capture:
                    captures_dir = self.output_dir / "frame_captures"
                    capture_file = captures_dir / f"{func_name}.jsonl"
                    frame_capture.save_jsonl(capture_file, metadata={
                        'idea': desc,
                        'validation': True
                    })
                    debug(f"  ├─ ✓ Frames captured ({len(frame_capture.get_frames())} frames)")
                
                animation = Animation(func_name, desc, code, namespace[func_name])
                self.queue.put(animation)
                
                metrics = analyze_code(code, func_name)
                self.telemetry.log_generation(
                    generation_id=func_name,
                    timestamp=time.time(),
                    idea=desc,
                    success=True,
                    attempt=attempt,
                    **metrics
                )
                
                self.telemetry.log_training_example(
                    prompt=f"Create VFD animation: {desc} (spatial patterns and full 20x2 display).",
                    response=code,
                    metadata=metrics
                )
                
                self.state.save(func_name, desc, "success", "")
                
                if self.progress:
                    self.progress.set_progress(self.gen_count * 1.0)
                
                debug(f"  └─ ✓ Queued successfully")
                return
                
            except Exception as e:
                debug(f"  ├─ ✗ Compilation failed: {str(e)[:100]}")
                all_errors.append(f"Compile: {str(e)[:100]}")
                continue
        
        debug(f"  └─ ✗ All {MAX_RETRIES} attempts failed")
        final_error = '\n'.join(all_errors[-3:])
        
        self.telemetry.log_generation(
            generation_id=func_name,
            timestamp=time.time(),
            idea=desc,
            success=False,
            attempt=MAX_RETRIES,
            error=final_error
        )
        
        self.state.save(func_name, desc, "failure", final_error)
        
        if self.progress:
            self.progress.set_progress(self.gen_count * 1.0)

    def generate_one_singleshot(self):
        """Generate single animation for single-shot mode"""
        desc = generate_idea()
        func_name = f"anim_{int(time.time())}_{random.randint(1000,9999)}"
        code_file = self.output_dir / f"{func_name}.py"
        
        all_errors = []
        
        for attempt in range(1, MAX_RETRIES + 1):
            code, gen_error, raw_response = generate_code(
                self.prompt, desc, func_name, attempt, all_errors, self.output_dir, self.progress
            )
            
            if not code:
                debug(f"  ├─ ✗ Code generation failed: {gen_error}")
                all_errors.append(f"Gen[{attempt}]: {gen_error}")
                continue
            
            debug(f"  ├─ ✓ Code received ({len(code)} chars)")
            
            try:
                code_file.write_text(code)
                debug(f"  ├─ ✓ Saved to {code_file.name}")
            except Exception as e:
                debug(f"  ├─ ✗ Save failed: {e}")
                all_errors.append(f"Save: {e}")
                continue
            
            valid, syntax_error = validate_syntax(code)
            if not valid:
                debug(f"  ├─ ✗ Syntax validation failed: {syntax_error}")
                all_errors.append(f"Syntax: {syntax_error}")
                continue
            
            debug(f"  ├─ ✓ Syntax valid")
            
            try:
                namespace = {'DiffAnimator': DiffAnimator, 'random': random, 'math': __import__('math')}
                exec(code, namespace)
                
                if func_name not in namespace:
                    debug(f"  ├─ ✗ Function not found in namespace")
                    all_errors.append("Function missing")
                    continue
                
                debug(f"  ├─ ✓ Compiled successfully")
                
                # ★ MODIFIED: Runtime validation now returns frame capture
                valid_runtime, runtime_error, frame_capture = validate_runtime(namespace[func_name], func_name)
                if not valid_runtime:
                    debug(f"  ├─ ✗ Runtime validation failed: {runtime_error}")
                    all_errors.append(f"Runtime: {runtime_error}")
                    continue
                
                # ★ NEW: Save captured frames
                if frame_capture:
                    captures_dir = self.output_dir / "frame_captures"
                    capture_file = captures_dir / f"{func_name}.jsonl"
                    frame_capture.save_jsonl(capture_file, metadata={
                        'idea': desc,
                        'validation': True
                    })
                    debug(f"  ├─ ✓ Frames captured ({len(frame_capture.get_frames())} frames)")
                
                animation = Animation(func_name, desc, code, namespace[func_name])
                self.queue.put(animation)
                
                metrics = analyze_code(code, func_name)
                self.telemetry.log_generation(
                    generation_id=func_name,
                    timestamp=time.time(),
                    idea=desc,
                    success=True,
                    attempt=attempt,
                    **metrics
                )
                
                self.telemetry.log_training_example(
                    prompt=f"Create VFD animation: {desc} (spatial patterns and full 20x2 display).",
                    response=code,
                    metadata=metrics
                )
                
                self.state.save(func_name, desc, "success", "")
                
                if self.progress:
                    self.progress.set_progress(MAX_RETRIES)
                
                debug(f"  └─ ✓ Queued successfully")
                return
                
            except Exception as e:
                debug(f"  ├─ ✗ Compilation failed: {str(e)[:100]}")
                all_errors.append(f"Compile: {str(e)[:100]}")
                continue
        
        debug(f"  └─ ✗ All {MAX_RETRIES} attempts failed")
        final_error = '\n'.join(all_errors[-3:])
        
        self.telemetry.log_generation(
            generation_id=func_name,
            timestamp=time.time(),
            idea=desc,
            success=False,
            attempt=MAX_RETRIES,
            error=final_error
        )
        
        self.state.save(func_name, desc, "failure", final_error)
        
        if self.progress:
            self.progress.set_progress(MAX_RETRIES)


class DisplayController:
    """Controls VFD display and animation playback"""
    def __init__(self, animation_queue: queue.Queue, state: State, keyboard: KeyboardListener = None):
        self.queue = animation_queue
        self.state = state
        self.keyboard = keyboard
        self.display = None
        self.animator = None
        self.running = False
        self.play_count = 0
        self.loading_active = False

    def start(self):
        try:
            if VFD_DEVICE == "simulator":
                self.display = CD5220.create_simulator_only(debug=False, render_console=False)
                ok(f"Using simulator (no hardware)")
            else:
                self.display = CD5220(VFD_DEVICE, baudrate=VFD_BAUDRATE, debug=False)
                ok(f"Display connected: {VFD_DEVICE}")

            hardware_animator = DiffAnimator(self.display, frame_rate=FRAME_RATE, render_console=False)
            
            # ★ MODIFIED: Enable frame capture if preview or simulator mode
            capture_enabled = PREVIEW_MODE or (VFD_DEVICE == "simulator")
            self.animator = DualAnimator(hardware_animator, PREVIEW_MODE, capture_frames=capture_enabled)
            self.animator.clear_display()

            if PREVIEW_MODE:
                ok("Console output enabled")

        except Exception as e:
            err(f"Display init failed: {e}")
            raise

    def show_loading(self, progress_tracker: ProgressTracker):
        """Show loading bar during initial generation"""
        try:
            self.loading_active = True
            last_percent = -1
            
            while self.loading_active:
                current, target = progress_tracker.get_progress()
                
                if current >= target:
                    line1 = "LOADING 100%".center(20)
                    line2 = "██████████".center(20)
                    self.animator.write_frame(line1, line2)
                    time.sleep(0.15)
                    self.animator.clear_display()
                    return
                
                percent = (current / target) if target > 0 else 0
                percent_int = int(percent * 100)
                
                if percent_int != last_percent:
                    filled = int(percent * 10)
                    line1 = f"LOADING {percent_int:03d}%".center(20)
                    bar = "█" * filled + " " * (10 - filled)
                    line2 = f"[{bar}]".center(20)
                    self.animator.write_frame(line1, line2)
                    last_percent = percent_int
                
                time.sleep(0.1)
                
        except Exception as e:
            debug(f"Loading error: {e}")
        finally:
            self.loading_active = False

    def run(self):
        """Continuous mode playback"""
        self.running = True
        
        while self.running:
            try:
                try:
                    animation = self.queue.get(timeout=20)
                except queue.Empty:
                    warn("Queue empty")
                    self.show_placeholder()
                    continue
                
                self.play_count += 1
                queued_depth = self.queue.qsize()
                info(f"▶ #{self.play_count}: {animation.desc} | Queue: {queued_depth} | {self.state.stats()}")
                
                try:
                    animation.run(self.animator, ANIMATION_DURATION)
                    
                    if self.keyboard and self.keyboard.check_and_clear():
                        self.bookmark_animation(animation)
                    
                    if self.keyboard and self.keyboard.check_and_clear_downvote():
                        self.downvote_animation(animation)
                    
                    # ★ NEW: Save playback frame capture if enabled
                    frame_cap = self.animator.get_frame_capture()
                    if frame_cap and len(frame_cap.get_frames()) > 0:
                        captures_dir = Path("generated_animations") / "frame_captures"
                        capture_file = captures_dir / f"{animation.func_name}_playback.jsonl"
                        frame_cap.save_jsonl(capture_file, metadata={
                            'idea': animation.desc,
                            'playback': True,
                            'duration': ANIMATION_DURATION
                        })
                        debug(f"  └─ ✓ Playback frames saved ({len(frame_cap.get_frames())} frames)")
                    
                except Exception as e:
                    err(f"Playback error: {e}")
                finally:
                    self.animator.clear_display()
                    time.sleep(0.2)
                    
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                err(f"Display error: {e}")
                time.sleep(1)

    def run_single(self, animation: Animation):
        """Single-shot mode - loop one animation forever"""
        self.running = True
        info(f"Looping: {animation.desc}")
        loop_count = 0
        
        while self.running:
            try:
                loop_count += 1
                if loop_count % 10 == 0:
                    info(f"Loop {loop_count}: {animation.desc}")
                
                animation.run(self.animator, ANIMATION_DURATION)
                
                if self.keyboard and self.keyboard.check_and_clear():
                    self.bookmark_animation(animation)
                
                if self.keyboard and self.keyboard.check_and_clear_downvote():
                    self.downvote_animation(animation)
                
                # ★ NEW: Save playback frame capture if enabled
                frame_cap = self.animator.get_frame_capture()
                if frame_cap and len(frame_cap.get_frames()) > 0 and loop_count == 1:
                    captures_dir = Path("generated_animations") / "frame_captures"
                    capture_file = captures_dir / f"{animation.func_name}_playback.jsonl"
                    frame_cap.save_jsonl(capture_file, metadata={
                        'idea': animation.desc,
                        'playback': True,
                        'single_shot': True
                    })
                    debug(f"  └─ ✓ Playback frames saved ({len(frame_cap.get_frames())} frames)")
                
                self.animator.clear_display()
                time.sleep(0.2)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                err(f"Playback error: {e}")
                time.sleep(1)

    def show_placeholder(self):
        """Show waiting message when queue is empty"""
        try:
            for i in range(60):
                if not self.queue.empty():
                    break
                dots = "." * ((i % 4) + 1)
                self.animator.write_frame(f"GENERATING{dots}".ljust(20), " " * 20)
                time.sleep(0.5)
            self.animator.clear_display()
        except:
            pass

    def stop(self):
        self.running = False
        if self.animator:
            try:
                self.animator.clear_display()
            except:
                pass

    def bookmark_animation(self, animation):
        """Log bookmark event to telemetry"""
        try:
            telemetry_dir = Path("generated_animations/telemetry")
            telemetry_dir.mkdir(parents=True, exist_ok=True)
            events_file = telemetry_dir / "events.jsonl"
            
            bookmark_event = {
                "timestamp": datetime.now().isoformat(),
                "message": "bookmark",
                "generation_id": animation.func_name,
                "idea": animation.desc,
                "bookmarked": True,
                "bookmark_time": time.time()
            }
            
            with open(events_file, 'a') as f:
                f.write(json.dumps(bookmark_event) + '\n')
            
            ok(f"★ Bookmarked: {animation.desc[:40]}")
        except Exception as e:
            err(f"Bookmark failed: {e}")

    def downvote_animation(self, animation):
        """Log downvote event to telemetry"""
        try:
            telemetry_dir = Path("generated_animations/telemetry")
            telemetry_dir.mkdir(parents=True, exist_ok=True)
            events_file = telemetry_dir / "events.jsonl"
            
            downvote_event = {
                "timestamp": datetime.now().isoformat(),
                "message": "downvote",
                "generation_id": animation.func_name,
                "idea": animation.desc,
                "downvoted": True,
                "downvote_time": time.time()
            }
            
            with open(events_file, 'a') as f:
                f.write(json.dumps(downvote_event) + '\n')
            
            err(f"✗ Downvoted: {animation.desc[:40]}")
        except Exception as e:
            err(f"Downvote failed: {e}")


def init_check():
    """Validate system requirements before starting"""
    header("Initialization")
    
    try:
        from cd5220 import CD5220, DiffAnimator
        ok("cd5220 module OK")
    except ImportError as e:
        err(f"cd5220 import failed: {e}")
        sys.exit(1)

    if VFD_DEVICE != "simulator":
        device_path = Path(VFD_DEVICE)
        if not device_path.exists():
            err(f"Device not found: {VFD_DEVICE}")
            sys.exit(1)
        
        if not (os.access(device_path, os.R_OK) and os.access(device_path, os.W_OK)):
            err(f"No permission: {VFD_DEVICE}")
            sys.exit(1)
        
        ok(f"Device OK: {VFD_DEVICE}")

    try:
        resp = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        model_names = [m["name"] for m in models]
        if MODEL not in model_names:
            err(f"Model not found: {MODEL}")
            sys.exit(1)
        ok(f"Model ready: {MODEL}")
    except Exception as e:
        err(f"Ollama error: {e}")
        sys.exit(1)
    
    if CUSTOM_IDEA:
        info(f"Custom idea: {CUSTOM_IDEA} (single-shot mode)")
    
    info(f"Config: {ANIMATION_DURATION}s animations, queue size {QUEUE_SIZE}")


def main():
    global VERBOSE, ANIMATION_DURATION, PREVIEW_MODE, FRAME_RATE, CUSTOM_IDEA
    
    parser = argparse.ArgumentParser(description="VFD Animation Agent v4.16")
    parser.add_argument('-d', '--duration', type=float, help="Animation duration in seconds")
    parser.add_argument('-f', '--fps', type=int, help="Frame rate in Hz")
    parser.add_argument('-p', '--prompt', type=str, default=DEFAULT_PROMPT_FILE, help="Prompt file path")
    parser.add_argument('--idea', type=str, help="Custom animation idea (single-shot mode)")
    parser.add_argument('--preview', action='store_true', help="Show console output")
    parser.add_argument('-v', '--verbose', action='store_true', help="Verbose logging")
    parser.add_argument('--replay', nargs='?', const='generated_animations', help="Replay existing animations from folder (default: generated_animations)")
    parser.add_argument('--version', action='version', version='VFD Agent v4.16')
    
    args = parser.parse_args()
    
    VERBOSE = args.verbose
    PREVIEW_MODE = args.preview
    CUSTOM_IDEA = args.idea
    
    if args.duration:
        ANIMATION_DURATION = args.duration
    if args.fps:
        FRAME_RATE = args.fps
    
    prompt = load_prompt(Path(args.prompt))
    output_dir = Path(__file__).parent / "generated_animations"
    output_dir.mkdir(exist_ok=True)
    
    state = State(output_dir / "agent_state.json")
    animation_queue = queue.Queue(maxsize=QUEUE_SIZE)
    
    init_check()
    
    if args.replay:
        header("Replay Mode")
        replay_dir = Path(args.replay)
        if not replay_dir.exists():
            err(f"Replay directory not found: {replay_dir}")
            sys.exit(1)
        
        anim_files = sorted(replay_dir.glob("anim_*.py"))
        if not anim_files:
            err(f"No animation files found in {replay_dir}")
            sys.exit(1)
        
        info(f"Found {len(anim_files)} animations to replay")
        
        if PREVIEW_MODE:
            info("Console output enabled")
        
        info("Press 'b' to bookmark, 'd' to downvote, Ctrl+C to stop")
        
        keyboard = KeyboardListener()
        display = DisplayController(queue.Queue(), state, keyboard)
        
        try:
            keyboard.start()
            display.start()
            
            animations = []
            for anim_file in anim_files:
                try:
                    namespace = {'DiffAnimator': DiffAnimator, 'random': random, 'math': __import__('math')}
                    with open(anim_file) as f:
                        code = f.read()
                    exec(code, namespace)
                    
                    func_name = anim_file.stem
                    if func_name in namespace:
                        anim = Animation(func_name, func_name, code, namespace[func_name])
                        animations.append(anim)
                except Exception as e:
                    warn(f"Skipping {anim_file.name}: {e}")
            
            if not animations:
                err("No valid animations loaded")
                sys.exit(1)
            
            ok(f"Loaded {len(animations)} animations")
            
            play_count = 0
            while True:
                for animation in animations:
                    play_count += 1
                    info(f"▶ {play_count}: {animation.desc}")
                    
                    try:
                        animation.run(display.animator, ANIMATION_DURATION)
                        
                        if keyboard.check_and_clear():
                            display.bookmark_animation(animation)
                        
                        if keyboard.check_and_clear_downvote():
                            display.downvote_animation(animation)
                        
                        # ★ NEW: Save replay frame capture if enabled
                        frame_cap = display.animator.get_frame_capture()
                        if frame_cap and len(frame_cap.get_frames()) > 0:
                            captures_dir = Path("generated_animations") / "frame_captures"
                            capture_file = captures_dir / f"{animation.func_name}_replay.jsonl"
                            frame_cap.save_jsonl(capture_file, metadata={
                                'replay': True,
                                'source': str(anim_file)
                            })
                            debug(f"  └─ ✓ Replay frames saved")
                        
                    except Exception as e:
                        err(f"Playback error: {e}")
                    finally:
                        display.animator.clear_display()
                        time.sleep(0.2)
        
        except KeyboardInterrupt:
            info("\n...")
        except Exception as e:
            err(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            keyboard.stop()
            display.stop()
            info("Stopped")
        
        sys.exit(0)
    
    if CUSTOM_IDEA:
        header("Single-Shot Mode")
        info("Generating ONE animation, will loop forever")
        if PREVIEW_MODE:
            info("Console output enabled")
        info("Press 'b' to bookmark, 'd' to downvote, Ctrl+C to stop")
        
        progress = ProgressTracker(MAX_RETRIES)
        generator = Generator(animation_queue, state, output_dir, prompt, progress)
        keyboard = KeyboardListener()
        display = DisplayController(animation_queue, state, keyboard)
        
        try:
            keyboard.start()
            display.start()
            
            info("Generating animation...")
            loading_thread = threading.Thread(target=display.show_loading, args=(progress,), daemon=True)
            loading_thread.start()
            
            generator.generate_one_singleshot()
            
            display.loading_active = False
            loading_thread.join(timeout=0.5)
            
            if animation_queue.qsize() != 1:
                err("Generation failed after max retries")
                err(f"Check generated_animations/failed_*.txt for details")
                sys.exit(1)
            
            animation = animation_queue.get()
            ok(f"Generated: {animation.desc}")
            
            display.run_single(animation)
            
        except KeyboardInterrupt:
            info("\n...")
        except Exception as e:
            err(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            keyboard.stop()
            display.stop()
            info("Stopped")
    
    else:
        header("Continuous Generation Mode")
        info("Display will NEVER be blank")
        info("Animations generate in background")
        if PREVIEW_MODE:
            info("Console output enabled")
        info("Press 'b' to bookmark, 'd' to downvote, Ctrl+C to stop")
        
        progress = ProgressTracker(QUEUE_SIZE)
        generator = Generator(animation_queue, state, output_dir, prompt, progress)
        keyboard = KeyboardListener()
        display = DisplayController(animation_queue, state, keyboard)
        
        try:
            keyboard.start()
            display.start()
            
            info("Pre-generating initial animations...")
            loading_thread = threading.Thread(target=display.show_loading, args=(progress,), daemon=True)
            loading_thread.start()
            
            generator.start()
            
            wait_start = time.time()
            while animation_queue.qsize() < 1:
                if time.time() - wait_start > 120:
                    warn("Initial generation taking longer than expected...")
                    wait_start = time.time()
                time.sleep(0.1)
            
            display.loading_active = False
            loading_thread.join(timeout=0.5)
            
            ok(f"Queue filled ({animation_queue.qsize()} ready)")
            
            display.run()
            
        except KeyboardInterrupt:
            info("\n...")
        except Exception as e:
            err(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                keyboard.stop()
                generator.stop()
                display.stop()
                info("Stopped")
            except KeyboardInterrupt:
                sys.exit(0)


if __name__ == '__main__':
    main()
