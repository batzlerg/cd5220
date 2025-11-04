# to_video.py — VFD Animation Renderer

Convert generated animation Python files to MP4 videos with proper VFD-style formatting.

## Setup

```

chmod +x to_video.py

```

**Dependencies:**
- FFmpeg: `sudo apt-get install ffmpeg`
- Python 3.6+
- Pillow: `pip install Pillow` (usually already installed)
- cd5220 module (from local repo)

## Usage

### Render all new animations
```

./to_video.py

```
Skips existing videos in `generated_animations/videos/`. Safe to run repeatedly.

### Force re-render everything
```

./to_video.py --force

```

### Custom animation duration and frame rate
```

./to_video.py -d 15 --fps 8

```

### Render specific files only
```

./to_video.py anim_1234567890.py anim_9876543210.py

```

## Output

- **Location:** `generated_animations/videos/*.mp4`
- **Format:** 640×200px, H.264, yuv420p, 6 FPS (default)
- **Appearance:** Cyan text on black with balanced 40px side margins and 45px top margin
- **Frames:** Each animation becomes a short video matching its execution duration

## What happens

1. Loads each `.py` animation file from `generated_animations/`
2. Executes the animation function via a mock display that captures frames
3. Renders each frame as an image (monospace font, proper spacing)
4. Pipes raw RGB data directly to FFmpeg for MP4 encoding
5. Saves output to `videos/` with idempotent caching

## Troubleshooting

**FFmpeg not found:**
```

sudo apt-get install ffmpeg

```

**Font path error:**
Script looks for DejaVu Sans Mono Bold at `/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf`. Update `FONT_PATH` in the script if your system stores fonts elsewhere.

**Corrupt animation files (emojis/markdown):**
Script skips these safely and reports them. No action needed—they're filtered automatically.

**Videos not rendering:**
Check FFmpeg is working: `ffmpeg -version`

## Notes

- Idempotency: Existing MP4s are never overwritten unless `--force` is used
- Frame count varies with animation duration and FPS
- Character layout: 20 columns × 2 rows with proper monospace kerning
- Suitable for: Visual QA, dataset generation, training models on VFD aesthetics
