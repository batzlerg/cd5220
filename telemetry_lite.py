#!/usr/bin/env python3
"""
Lightweight telemetry system for VFD agent using JSON logging
Zero-config, JSONL output, training-data ready
"""

import logging
import time
from pathlib import Path
from pythonjsonlogger import jsonlogger

class VFDTelemetry:
    """Simple JSON-based telemetry using standard Python logging"""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Events log (all generation attempts)
        self.events_logger = self._setup_logger(
            'vfd_events',
            self.log_dir / 'events.jsonl'
        )

        # Training data log (successful generations only)
        self.training_logger = self._setup_logger(
            'vfd_training',
            self.log_dir / 'training.jsonl'
        )

    def _setup_logger(self, name: str, filepath: Path) -> logging.Logger:
        """Setup JSON logger with custom format"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False

        handler = logging.FileHandler(filepath)
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(message)s',
            timestamp=True
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def log_generation(self, **kwargs):
        """
        Log a generation event with arbitrary fields

        Example:
            telemetry.log_generation(
                generation_id='anim_123',
                timestamp=time.time(),
                idea='cascade rain',
                success=True,
                code_length=450
            )
        """
        # Add timestamp if not provided
        if 'timestamp' not in kwargs:
            kwargs['timestamp'] = time.time()

        self.events_logger.info('generation', extra=kwargs)

    def log_training_example(self, prompt: str, response: str, metadata: dict = None):
        """
        Log successful generation as training data (Ollama-compatible format)

        Args:
            prompt: The prompt/idea description
            response: The generated code
            metadata: Optional metadata dict
        """
        record = {
            'prompt': prompt,
            'response': response,
            'timestamp': time.time()
        }

        if metadata:
            record['metadata'] = metadata

        self.training_logger.info('training_example', extra=record)

    def log_bookmark(self, generation_id: str, timestamp: float = None, idea: str = ""):
        """
        Log a bookmark event for an animation.
        Updates the events log with bookmark flag.

        Args:
            generation_id: Animation function name
            timestamp: Optional timestamp (defaults to current time)
            idea: Animation description (optional)
        """
        if timestamp is None:
            timestamp = time.time()

        bookmark_event = {
            'timestamp': timestamp,
            'message': 'bookmark',
            'generation_id': generation_id,
            'idea': idea,
            'bookmarked': True,
            'bookmark_time': timestamp
        }

        self.events_logger.info('bookmark', extra=bookmark_event)

if __name__ == '__main__':
    # Simple test
    import tempfile
    test_dir = Path(tempfile.mkdtemp())

    telemetry = VFDTelemetry(test_dir / 'telemetry')

    # Test event logging
    telemetry.log_generation(
        generation_id='test_001',
        idea='test pattern',
        success=True,
        code_length=100
    )

    # Test training logging
    telemetry.log_training_example(
        prompt='Create test animation',
        response='def test(): pass',
        metadata={'quality': 0.8}
    )

    # Test bookmark logging
    telemetry.log_bookmark(
        generation_id='test_001',
        idea='test pattern'
    )

    print(f"Test logs written to: {test_dir}")
    print(f"Events: {test_dir / 'telemetry/events.jsonl'}")
    print(f"Training: {test_dir / 'telemetry/training.jsonl'}")
