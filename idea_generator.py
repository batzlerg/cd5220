#!/usr/bin/env python3
"""
Natural language idea generator for VFD animations.
Reads explicit POS tags from idea.txt (word:pos format).
Fast, no NLTK dependency for POS detection.
"""

import random
from pathlib import Path
from typing import List, Dict

try:
    import inflect
    p = inflect.engine()
except ImportError:
    print("ERROR: inflect not installed")
    print("Install: pip3 install inflect")
    exit(1)


class IdeaGenerator:
    """Constructs phrases from explicitly-tagged word file"""
    
    def __init__(self, word_file: Path = Path('idea.txt')):
        self.word_file = word_file
        self.vocabulary = {'verbs': [], 'nouns': [], 'adjectives': []}
        self._load_vocabulary()
    
    def _load_vocabulary(self):
        """Load words from file with explicit POS tags (word:pos format)"""
        if not self.word_file.exists():
            print(f"ERROR: {self.word_file} not found")
            print("Create idea.txt with format: word:pos (pos = v/n/a)")
            exit(1)
        
        words_loaded = 0
        skipped = 0
        with open(self.word_file) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Parse word:pos format
                if ':' not in line:
                    skipped += 1
                    continue
                
                parts = line.split(':', 1)
                if len(parts) != 2:
                    skipped += 1
                    continue
                
                word, pos_tag = parts
                word = word.strip()
                pos_tag = pos_tag.strip().lower()
                
                # Map to categories
                if pos_tag == 'v':
                    self.vocabulary['verbs'].append(word)
                    words_loaded += 1
                elif pos_tag == 'n':
                    self.vocabulary['nouns'].append(word)
                    words_loaded += 1
                elif pos_tag == 'a':
                    self.vocabulary['adjectives'].append(word)
                    words_loaded += 1
                else:
                    skipped += 1
        
        # Remove duplicates
        for pos in self.vocabulary:
            self.vocabulary[pos] = list(set(self.vocabulary[pos]))
        
        # Report stats
        if skipped > 0:
            print(f"WARNING: Skipped {skipped} lines (missing or invalid :pos tags)")
        
        print(f"Loaded {words_loaded} words: "
              f"{len(self.vocabulary['verbs'])} verbs, "
              f"{len(self.vocabulary['nouns'])} nouns, "
              f"{len(self.vocabulary['adjectives'])} adjectives")
        
        # Validate minimum words
        if len(self.vocabulary['verbs']) < 5:
            print(f"ERROR: Only {len(self.vocabulary['verbs'])} verbs found (need 5+)")
            exit(1)
        if len(self.vocabulary['nouns']) < 5:
            print(f"ERROR: Only {len(self.vocabulary['nouns'])} nouns found (need 5+)")
            exit(1)
    
    def generate(self, min_words: int = 2, max_words: int = 4) -> str:
        """
        Generate phrase with constraints.
        
        Args:
            min_words: Minimum phrase length (default: 2)
            max_words: Maximum phrase length (default: 4)
        
        Returns:
            Natural language phrase (e.g., "mirrored bouncing sparks")
        """
        target_length = random.randint(min_words, max_words)
        components = []
        
        # Decide structure randomly
        has_verb = random.random() < 0.8  # 80% chance of verb
        num_adjectives = random.choices([0, 1, 2], weights=[0.3, 0.5, 0.2])[0]
        
        # Add adjectives
        if self.vocabulary['adjectives']:
            for _ in range(min(num_adjectives, len(self.vocabulary['adjectives']))):
                if len(components) < target_length - 1:  # Leave room for noun
                    adj = random.choice(self.vocabulary['adjectives'])
                    if adj not in components:
                        components.append(adj)
        
        # Add verb (as present participle using inflect)
        if has_verb and self.vocabulary['verbs'] and len(components) < target_length - 1:
            verb = random.choice(self.vocabulary['verbs'])
            verb_ing = p.present_participle(verb)
            if verb_ing:
                components.append(verb_ing)
            else:
                # Fallback if inflect fails
                components.append(verb + 'ing')
        
        # Add noun(s) to reach target length
        while len(components) < target_length and self.vocabulary['nouns']:
            noun = random.choice(self.vocabulary['nouns'])
            if noun not in components:
                components.append(noun)
        
        # Ensure at least one noun exists
        if not components or not any(word in self.vocabulary['nouns'] for word in components):
            if self.vocabulary['nouns']:
                components.append(random.choice(self.vocabulary['nouns']))
        
        return ' '.join(components)
    
    def list_vocabulary(self):
        """Print current vocabulary for debugging"""
        for pos, words in self.vocabulary.items():
            print(f"\n{pos.upper()} ({len(words)}):")
            print(", ".join(sorted(words)))


# Singleton instance
_generator = None

def get_generator() -> IdeaGenerator:
    """Get or create global generator instance"""
    global _generator
    if _generator is None:
        _generator = IdeaGenerator()
    return _generator


def generate_idea() -> str:
    """Public API: generate animation idea phrase"""
    return get_generator().generate(min_words=2, max_words=4)


# CLI test mode
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'list':
        get_generator().list_vocabulary()
    else:
        # Generate 10 sample ideas
        print("\nSample ideas:")
        for i in range(10):
            print(f"  {i+1}. {generate_idea()}")
