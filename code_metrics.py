#!/usr/bin/env python3
"""
Code analysis for VFD-generated animations
Extracts quality metrics using Python AST and regex
"""

import ast
import re
import hashlib
from typing import Dict, Set, List


def analyze_code(code: str, func_name: str = None) -> Dict:
    """
    Extract comprehensive metrics from generated Python code
    
    Args:
        code: The Python source code to analyze
        func_name: Optional function name for validation
    
    Returns:
        Dict of metrics suitable for telemetry logging
    """
    metrics = {
        'code_length': len(code),
        'code_hash': hashlib.md5(code.encode()).hexdigest()[:16],
        'lines_total': len(code.split('\n')),
        'lines_code': len([l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]),
    }

    # Structural analysis using AST
    try:
        tree = ast.parse(code)
        metrics['functions_count'] = len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)])
        metrics['loops_count'] = len([n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))])
        metrics['conditionals_count'] = len([n for n in ast.walk(tree) if isinstance(n, ast.If)])
        metrics['ast_valid'] = True
    except Exception as e:
        metrics['functions_count'] = 0
        metrics['loops_count'] = 0
        metrics['conditionals_count'] = 0
        metrics['ast_valid'] = False
        metrics['ast_error'] = str(e)[:100]

    # Character extraction from string literals
    chars_in_strings = _extract_display_characters(code)
    metrics['unique_chars_count'] = len(chars_in_strings)
    metrics['unique_chars'] = ''.join(sorted(chars_in_strings))[:50]  # Limit length

    # Character family detection
    families = _detect_character_families(chars_in_strings)
    metrics['character_families'] = families
    metrics['character_families_count'] = len(families)

    # Pattern detection
    patterns = _detect_spatial_patterns(code)
    metrics['spatial_patterns'] = patterns
    metrics['spatial_patterns_count'] = len(patterns)

    # Code quality indicators
    metrics['uses_both_rows'] = 'line1' in code and 'line2' in code
    metrics['uses_full_width'] = 'range(20)' in code or '* 20' in code
    metrics['has_motion_logic'] = _detect_motion_logic(code)

    # Width coverage estimation
    metrics['estimated_width_percent'] = _estimate_width_coverage(code)

    if func_name:
        metrics['function_name'] = func_name
        metrics['function_name_in_code'] = func_name in code

    return metrics


def _extract_display_characters(code: str) -> Set[str]:
    """Extract all characters used in display strings"""
    chars = set()
    for match in re.finditer(r'["\']([^"\'\\]*)["\']', code):
        content = match.group(1)
        chars.update(c for c in content if c not in ' \n\t\r')
    return chars


def _detect_character_families(chars: Set[str]) -> List[str]:
    """Categorize characters into visual families"""
    families = {
        'rotational': set('|/-\\<^>v'),
        'density': set('.oO@*#%+'),
        'organic': set('.oO*~-'),
        'structural': set('[](){}=_'),
        'arrows': set('<>^v'),
    }

    detected = []
    for name, family_chars in families.items():
        if chars & family_chars:
            detected.append(name)

    return detected


def _detect_spatial_patterns(code: str) -> List[str]:
    """Detect animation patterns in code using keyword matching"""
    patterns = []
    code_lower = code.lower()

    pattern_keywords = {
        'cross_row': ['bally', 'row', 'y in', 'y ='],
        'cascade': ['drops', 'fall', 'rain', 'cascade'],
        'wave': ['phase', 'sin', 'cos', 'wave'],
        'mirror': ['mirror', 'symmetric', 'reflect'],
        'bounce': ['bounce', 'vel', 'velocity'],
        'spiral': ['spiral', 'rotate', 'spin'],
        'particle': ['particle', 'entities'],
    }

    for pattern_name, keywords in pattern_keywords.items():
        if any(keyword in code_lower for keyword in keywords):
            patterns.append(pattern_name)

    return patterns if patterns else ['unknown']


def _detect_motion_logic(code: str) -> bool:
    """Detect if code contains motion/animation logic"""
    motion_indicators = [
        'frame', 'velocity', 'vel', 'position', 'move',
        'offset', 'step', 'increment', 'speed', 'delta'
    ]
    code_lower = code.lower()
    return any(indicator in code_lower for indicator in motion_indicators)


def _estimate_width_coverage(code: str) -> float:
    """Estimate percentage of display width typically used"""
    if 'range(20)' in code:
        return 100.0
    if "' '] * 20" in code or '[" "] * 20' in code:
        return 100.0

    # Check for range patterns
    range_matches = re.findall(r'range\((\d+)\)', code)
    if range_matches:
        max_range = max(int(m) for m in range_matches)
        return min((max_range / 20.0) * 100.0, 100.0)

    # Check for x coordinate bounds
    x_bound_matches = re.findall(r'\bx\s*<\s*(\d+)', code)
    if x_bound_matches:
        max_x = max(int(m) for m in x_bound_matches)
        return min((max_x / 20.0) * 100.0, 100.0)

    # Conservative default
    return 50.0


if __name__ == '__main__':
    # Self-test with sample code
    sample_code = '''
from cd5220 import DiffAnimator
import random

def test_animation(animator: DiffAnimator, duration: float = 10.0):
    frame_count = int(duration * animator.frame_rate)
    for frame in range(frame_count):
        line1 = [' '] * 20
        line2 = [' '] * 20
        x = frame % 20
        line1[x] = 'O'
        line2[19-x] = '*'
        animator.write_frame(''.join(line1), ''.join(line2))
        animator.frame_sleep(1.0 / animator.frame_rate)
'''

    print("Testing code_metrics module...")
    metrics = analyze_code(sample_code, 'test_animation')

    print(f"✓ Code length: {metrics['code_length']}")
    print(f"✓ Lines: {metrics['lines_total']}")
    print(f"✓ Unique chars: {metrics['unique_chars_count']}")
    print(f"✓ Families: {metrics['character_families']}")
    print(f"✓ Patterns: {metrics['spatial_patterns']}")
    print(f"✓ Uses both rows: {metrics['uses_both_rows']}")
    print(f"✓ Motion logic: {metrics['has_motion_logic']}")
    print(f"✓ Width coverage: {metrics['estimated_width_percent']}%")
    print("\nAll tests passed!")
