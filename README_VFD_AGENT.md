## VFD Animation Agent

A high-fidelity LLM-powered animation generation system for the CD5220 VFD customer display. The agent generates creative, spec-compliant ASCII animations through iterative AI collaboration with Ollama, featuring real-time runtime validation and continuous background generation.

***

## Overview

The agent operates in two distinct modes:

### Continuous Generation Mode (Default)

- Generates animations **infinitely** in the background
- Maintains a **queue** of pre-generated animations (configurable size)
- **Display never goes blank** - plays queued animations while new ones generate
- Ideal for gallery/art installation scenarios where variety matters
- Run: `./vfd_agent.py`


### Single-Shot Mode (Custom Ideas)

- Generates **exactly ONE animation** based on a custom idea
- Loops that animation **forever** until interrupted
- Useful for testing, refinement, or showcasing a specific concept
- Run: `./vfd_agent.py --idea "fighting beavers"`

***

## Quick Start

### Basic Usage

```bash
# Infinite random animations on hardware
./vfd_agent.py

# Custom animation idea (loops forever)
./vfd_agent.py --idea "seven ducks quacking"

# Test without hardware using simulator
VFD_DEVICE=simulator ./vfd_agent.py --idea "bouncing ball" --preview

# Verbose diagnostics
./vfd_agent.py --idea "exploding stars" -v --preview

# Adjust animation duration and frame rate
./vfd_agent.py -d 15 --fps 10 --idea "morphing shapes"
```


### Command-Line Options

| Flag | Description | Example |
| :-- | :-- | :-- |
| `-d, --duration` | Animation duration in seconds (default: 10.0) | `-d 15` |
| `-f, --fps` | Frame rate in Hz (default: 6) | `-f 10` |
| `-p, --prompt` | Path to Ollama prompt template (default: prompt.txt) | `-p custom_prompt.txt` |
| `--idea` | Custom animation idea (single-shot mode) | `--idea "bouncing balls"` |
| `--preview` | Show console output alongside display | `--preview` |
| `-v, --verbose` | Verbose logging with validation details | `-v` |
| `--version` | Show version and exit | `--version` |

### Environment Variables

| Variable | Description | Default |
| :-- | :-- | :-- |
| `VFD_DEVICE` | Display device path or `"simulator"` | `/dev/ttyUSB0` |
| `OLLAMA_API_BASE` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model to use for generation | `qwen2.5:3b` |
| `ANIMATION_DURATION` | Default animation duration | `10.0` |


***

## Testing Without Hardware

Set `VFD_DEVICE=simulator` to run without a physical display:

```bash
# Simulator only (no console output)
VFD_DEVICE=simulator ./vfd_agent.py --idea "test animation"

# Simulator with console preview
VFD_DEVICE=simulator ./vfd_agent.py --preview --idea "test animation"

# Continuous mode with simulator
VFD_DEVICE=simulator ./vfd_agent.py --preview
```

The `--preview` flag shows console output and works with both hardware and simulator modes.

***

## Display Output Options

| Command | Hardware Connection | Console Output |
| :-- | :-- | :-- |
| `./vfd_agent.py` | Required | No |
| `./vfd_agent.py --preview` | Required | Yes |
| `VFD_DEVICE=simulator ./vfd_agent.py` | Not used | No |
| `VFD_DEVICE=simulator ./vfd_agent.py --preview` | Not used | Yes |


***

## How It Works

### Generation Pipeline

Each animation goes through a **multi-stage validation pipeline** to ensure quality and correctness:

```
1. Code Generation
   ↓ (Ollama generates Python code)
2. Static Validation
   ↓ (Check for required functions, variables, motion)
3. Syntax Validation
   ↓ (Compile check)
4. Runtime Validation
   ↓ (Execute 600 frames @ 600fps to catch errors)
5. Queue → Display
```


### Stage Details

#### Code Generation

- **Model:** Ollama (configurable, default: `qwen2.5:3b`)
- **Tokens:** 2048 max output (prevents truncation)
- **Temperature:** Decreases with retry attempts (encourages diversity early, convergence on retry)
- **Stop sequences:** Only stops at `\nif __name__` (prevents premature termination)


#### Static Validation

Checks code structure WITHOUT execution:

- ✅ Contains `line1` and `line2` variables (2-row display)
- ✅ Uses full screen width (20 chars) - no minimal output
- ✅ Has motion logic (`frame`, `position`, `velocity`, etc.)
- ✅ Uses 4+ distinct characters for visual variety


#### Syntax Validation

Uses Python's `compile()` to catch parsing errors early.

#### Runtime Validation (The Critical Layer)

- Executes animation for **1 full second at 600fps** with **no sleep delays**
- Runs 600 frames in ~0.1 seconds wall time (instant feedback)
- Tests with a headless simulator (no hardware I/O)
- Catches:
    - 🛑 IndexError (array bounds violations like `list[20]` on 20-char display)
    - 🛑 ZeroDivisionError, AttributeError, TypeError
    - 🛑 Any other runtime exception in animation logic
- **If failed:** Full error passed to model, which learns and regenerates


### Retry Strategy

On validation failure, the agent provides **verbatim error context** to the model:

```
PREVIOUS ATTEMPT FAILED:
Runtime: IndexError: list assignment index out of range

Review the error above and generate corrected code.
```

The model interprets the error in context and generates corrected code, up to **MAX_RETRIES** (default: 5) attempts. This approach is **prompt-agnostic** - it works regardless of what constraints are specified in `prompt.txt`.

***

## Display Behavior

### Console Output Modes

#### Standard Mode (No Flags)

```
ℹ Loaded prompt: prompt.txt
✓ cd5220 module OK
✓ Device OK: /dev/ttyUSB0
✓ Model ready: qwen2.5-coder:14b
ℹ Config: 10.0s animations, queue size 2

========================================
Continuous Generation Mode
========================================
ℹ Display will NEVER be blank
ℹ Animations generate in background
ℹ Press Ctrl+C to stop
✓ Display connected: /dev/ttyUSB0

ℹ Pre-generating initial animations...
    LOADING 100%
    [==========]

✓ Queue filled (2 ready)
ℹ ▶ #1: dual row cascade rain | Queue: 1 | ✓8 ✗2
```


#### Verbose Mode (`-v`)

Adds detailed validation logs:

```
[DEBUG] Generate attempt 1/5: dual row cascade rain
[DEBUG]   ├─ ✓ Code received (823 chars)
[DEBUG]   ├─ ✓ Saved to anim_1762209785_2645.py
[DEBUG]   ├─ ✓ Syntax valid
[DEBUG]   ├─ ✓ Compiled successfully
[DEBUG]   ├─ ✓ Runtime validation passed (600 frames in 0.21s)
[DEBUG]   └─ ✓ Queued successfully
```

Shows **exactly** where failures occur and why.

#### Preview Mode (`--preview`)

Renders ASCII art to console alongside hardware output:

```
ℹ ▶ #1: dual row cascade rain | Queue: 1 | ✓8 ✗2
--------------------
 * . * . * . * . *
     * . * . * .
--------------------
```

Perfect for development and debugging.

***

## Configuration

### Prompt Template

The script uses a **prompt.txt** file containing the system prompt for the model. This establishes the constraint guidelines (2 rows, 20 chars, motion, variety, etc.).

```bash
./vfd_agent.py -p custom_prompt.txt  # Use different prompt
```

The retry mechanism is **prompt-agnostic** - it passes raw errors to the model without assuming specific constraint types, making it robust to prompt changes.

***

## Technical Details

### Single-Shot vs Continuous Modes

| Aspect | Single-Shot | Continuous |
| :-- | :-- | :-- |
| **Activation** | `--idea` flag | Default |
| **Queue** | Disabled | Enabled (size configurable) |
| **Generation** | Single animation, one attempt stream | Infinite background generation |
| **Display** | Loops same animation forever | Cycles through queue |
| **Use Case** | Testing, refinement, demos | Galleries, installations |
| **Progress** | Shows 0-100% across 5 attempts | Shows 0-100% per animation in queue |

### Performance

- **Code generation:** ~3-15 seconds per attempt (model-dependent)
- **Runtime validation:** ~0.1 seconds per animation (instant, headless)
- **Total time to first animation:** ~5-20 seconds (includes initial queue filling)
- **Queue refresh rate:** Continuous (generates next while displaying current)


### Failure Handling

All failures are logged to `generated_animations/agent_state.json`:

```json
{
  "generations": [
    {
      "timestamp": 1762209785,
      "function": "anim_1762209785_2645",
      "description": "dual row cascade rain",
      "status": "success",
      "error": ""
    },
    {
      "timestamp": 1762209742,
      "function": "anim_1762209742_1234",
      "description": "mirrored spiral bubbles",
      "status": "failure",
      "error": "Runtime: IndexError: list index out of range"
    }
  ],
  "success": 42,
  "failure": 3
}
```

Failed attempts also save **raw model output** for debugging:

```
generated_animations/failed_anim_1762209742_1234_attempt2.txt
```

Open these to inspect **exactly** what the model generated and why it failed.

***

## Animation Loop Architecture

Generated animations are **finite** (10 seconds by default). The agent script handles looping:

- **Continuous mode:** Cycles through queue forever
- **Single-shot mode:** Loops the same animation forever

**Why finite animations?**

- Simpler validation (test exactly 600 frames)
- Predictable resource usage
- Easier to interrupt cleanly

**Note:** The cd5220 library supports infinite state machines (while True loops), but the agent doesn't generate them for simplicity and consistency.

***

## Animation Spec

All generated animations must satisfy these constraints:

### Display Constraints

- **Format:** 2 rows × 20 characters
- **Frame rate:** 6 FPS (typical, configurable)
- **Duration:** 10 seconds (typical, configurable)


### Code Constraints

- **Language:** Python 3
- **Function signature:** `def anim_TIMESTAMP_RANDOM(animator: DiffAnimator, duration: float = 10.0)`
- **Required imports:** `DiffAnimator` from `cd5220`, `random`, `math`
- **Required calls:**
    - `animator.write_frame(line1: str, line2: str)` - Every frame
    - `animator.frame_sleep(seconds: float)` - Frame timing
- **Array bounds:** Indices MUST stay within `[0-19]` (20-char display)


### Visual Constraints

- **Dual-row usage:** Both `line1` and `line2` must be populated
- **Full width:** Animation should use most/all 20 chars per row
- **Motion:** Clear movement, position changes, velocity vectors
- **Character variety:** 4+ distinct characters for visual richness


### Character Set

The CD5220 supports **ASCII printable characters (32-126)**:

**Supported characters:**

- Letters: `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`
- Numbers: `0123456789`
- Symbols: `!"#$%&'()*+,-./:;<=>?@[$$^_{|}~`
- Spacing: ` ` (space)

**Common animation characters:**

- Dots/intensity: `.` `*` `o` `O` `@`
- Arrows: `^` `v` `<` `>`
- Lines: `|` `-` `+` `/` `\`
- Frames: `[` `]` `{` `}`

**Note:** Extended character sets (box-drawing, Unicode) are not supported by the hardware.

***

## Architecture

### Core Classes

**`Animation`**
Wrapper for generated animation functions with metadata (name, description, creation time).

**`Generator`**
Background thread that continuously generates and validates animations. Places successful ones in queue.

**`DisplayController`**
Manages hardware connection and playback. Plays animations from queue or runs single animation in loop.

**`DualAnimator`**
Combines hardware output with optional console preview for testing.

**`State`**
Persistent tracking of generation statistics (successes, failures) across runs.

**`ProgressTracker`**
Thread-safe progress indicator for loading bar display.

***

## Troubleshooting

### "No function found" errors

Usually means the model's response was truncated. Check the failed log file:

```bash
cat generated_animations/failed_anim_*_attempt1.txt | head -20
```

If response ends abruptly (e.g., just `import random\nimport math`), this was a model truncation. The agent will retry with error context.

### Runtime validation keeps failing

Check verbose mode to see WHICH validation failed:

```bash
./vfd_agent.py -v --idea "test idea" 2>&1 | grep "✗"
```

Common issues:

- **IndexError:** Bounds checking needed (ensure indices in `[0-19]`)
- **No motion logic:** Add `frame` counter or position variables
- **Insufficient character variety:** Use 4+ distinct chars


### Display shows "GENERATING..." for 60 seconds

Queue is empty and generator is stuck. Check:

- Ollama is running: `curl http://localhost:11434/api/tags`
- Model exists: `ollama pull qwen2.5:3b`
- Model loads: `ollama run qwen2.5:3b "hello"`


### Testing without hardware

Use simulator mode:

```bash
VFD_DEVICE=simulator ./vfd_agent.py --preview --idea "test"
```

If you see "Device not found: simulator", make sure you're using v4.12 or later.

***

## Examples

### Example 1: Hardware Gallery Mode

```bash
./vfd_agent.py --preview
```

Generates random animations continuously on hardware, with console preview for monitoring.

### Example 2: Simulator Development

```bash
VFD_DEVICE=simulator ./vfd_agent.py --idea "bouncing ball" --preview -v
```

Tests a specific concept without hardware, with full diagnostic output.

### Example 3: Production Deployment

```bash
export OLLAMA_MODEL=qwen2.5:14b  # Larger, higher quality
export ANIMATION_DURATION=15.0
./vfd_agent.py
```

Runs on actual hardware with larger model for production-quality animations.

### Example 4: Custom Prompt Testing

```bash
VFD_DEVICE=simulator ./vfd_agent.py -p experimental_prompt.txt --preview -v
```

Test a new prompt template with full visibility into generation process.

***

## TODO (maybe)

- Adaptive retry strategies based on error patterns
- Animation composition (stacking multiple animations)
- Real-time performance metrics dashboard
- Hardware-aware frame rate optimization
- Model selection from available Ollama models
- Reflection-based error diagnosis for complex failures

