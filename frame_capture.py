#!/usr/bin/env python3
"""
Frame capture and storage for VFD animations.
Captures frames from DiffAnimator during validation and playback.
"""

from typing import List, Tuple, Callable, Optional, Dict
from pathlib import Path
import json
import time
from datetime import datetime


class FrameCapture:
    """
    Transparent frame capture wrapper for DiffAnimator.
    
    Usage:
        animator = DiffAnimator(display)
        capture = FrameCapture(animator)
        
        # Use capture.animator instead of animator
        animation_func(capture.animator, duration=10.0)
        
        # Access captured frames
        frames = capture.get_frames()
        stats = capture.get_stats()
    """
    
    def __init__(self, animator, animation_id: str = None):
        """
        Initialize frame capture.
        
        Args:
            animator: DiffAnimator instance to wrap
            animation_id: Identifier for this capture session
        """
        self.wrapped_animator = animator
        self.animation_id = animation_id or f"capture_{int(time.time())}"
        self.frames: List[Tuple[str, str]] = []
        self.start_time = time.time()
        
        # Wrap write_frame to capture
        self._original_write_frame = animator.write_frame
        animator.write_frame = self._capturing_write_frame
        
        # Make wrapped animator accessible
        self.animator = animator
    
    def _capturing_write_frame(self, line1: str, line2: str):
        """Intercept write_frame calls to capture frames"""
        # Normalize to 20 characters
        line1_norm = line1[:20].ljust(20)
        line2_norm = line2[:20].ljust(20)
        
        # Store frame
        self.frames.append((line1_norm, line2_norm))
        
        # Call original
        return self._original_write_frame(line1, line2)
    
    def get_frames(self) -> List[Tuple[str, str]]:
        """Get all captured frames"""
        return self.frames.copy()
    
    def get_stats(self) -> Dict:
        """
        Analyze captured frames for quality metrics.
        
        Returns:
            Dictionary with frame statistics
        """
        if not self.frames:
            return {
                'total_frames': 0,
                'non_empty_frames': 0,
                'both_rows_active': 0,
                'empty_ratio': 1.0,
                'both_rows_ratio': 0.0,
                'empty_frame_indices': [],
                'single_row_indices': []
            }
        
        non_empty = 0
        both_rows = 0
        empty_indices = []
        single_row_indices = []
        
        for i, (line1, line2) in enumerate(self.frames):
            has_line1 = line1.strip()
            has_line2 = line2.strip()
            
            if has_line1 or has_line2:
                non_empty += 1
                
                if has_line1 and has_line2:
                    both_rows += 1
                else:
                    single_row_indices.append(i)
            else:
                empty_indices.append(i)
        
        total = len(self.frames)
        
        return {
            'total_frames': total,
            'non_empty_frames': non_empty,
            'both_rows_active': both_rows,
            'empty_ratio': 1.0 - (non_empty / total),
            'both_rows_ratio': both_rows / total,
            'empty_frame_indices': empty_indices,
            'single_row_indices': single_row_indices
        }
    
    def save_jsonl(self, output_path: Path, metadata: Dict = None):
        """
        Save captured frames to JSONL format.
        
        Args:
            output_path: Path to save file
            metadata: Additional metadata to include
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        full_metadata = {
            'animation_id': self.animation_id,
            'timestamp': self.start_time,
            'created_at': datetime.fromtimestamp(self.start_time).isoformat(),
            'total_frames': len(self.frames),
            'duration': time.time() - self.start_time
        }
        
        if metadata:
            full_metadata.update(metadata)
        
        with open(output_path, 'w') as f:
            # Write metadata header
            f.write(json.dumps({'_meta': full_metadata}) + '\n')
            
            # Write frames
            for frame_num, (line1, line2) in enumerate(self.frames):
                frame_obj = {
                    'frame': frame_num,
                    'line1': line1,
                    'line2': line2
                }
                f.write(json.dumps(frame_obj) + '\n')
    
    @classmethod
    def load_jsonl(cls, input_path: Path) -> Tuple[Dict, List[Tuple[str, str]]]:
        """
        Load frames from JSONL file.
        
        Args:
            input_path: Path to JSONL file
            
        Returns:
            Tuple of (metadata dict, frames list)
        """
        with open(input_path) as f:
            first_line = f.readline()
            meta_obj = json.loads(first_line)
            
            if '_meta' not in meta_obj:
                raise ValueError(f"Invalid JSONL format in {input_path}")
            
            metadata = meta_obj['_meta']
            frames = []
            
            for line in f:
                frame_data = json.loads(line)
                frames.append((frame_data['line1'], frame_data['line2']))
            
            return metadata, frames


def validate_frame_content(frames: List[Tuple[str, str]], 
                          empty_threshold: float = 0.7,
                          dual_row_threshold: float = 0.2) -> Tuple[bool, str]:
    """
    Validate frame content meets quality standards.
    
    Args:
        frames: List of (line1, line2) tuples
        empty_threshold: Maximum allowed empty frame ratio
        dual_row_threshold: Minimum required dual-row usage ratio
        
    Returns:
        Tuple of (valid, error_message)
    """
    if not frames:
        return False, "No frames captured"
    
    non_empty = sum(1 for l1, l2 in frames if l1.strip() or l2.strip())
    both_rows = sum(1 for l1, l2 in frames if l1.strip() and l2.strip())
    
    total = len(frames)
    empty_ratio = 1.0 - (non_empty / total)
    both_rows_ratio = both_rows / total
    
    if empty_ratio > empty_threshold:
        return False, f"Too many empty frames ({int(empty_ratio * 100)}% empty)"
    
    if both_rows_ratio < dual_row_threshold:
        return False, f"Poor dual-row usage ({int(both_rows_ratio * 100)}% use both rows)"
    
    return True, ""
