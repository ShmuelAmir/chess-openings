#!/usr/bin/env python3
filters = ['Anti-Sicilians For Black', 'Four Knights Sicilian']
opening = 'Sicilian Defense Old Sicilian Variation'

def normalize_word(word):
    """Normalize word for comparison (remove plural 's')."""
    if word.endswith('s') and len(word) > 3:
        return word[:-1]
    return word

# Test the improved logic
opening_lower = opening.lower()
for f in filters:
    f_lower = f.lower()
    print(f'Filter: {f}')
    print(f'  Exact containment: {f_lower in opening_lower or opening_lower in f_lower}')
    
    ignore_words = {'opening', 'defense', 'defence', 'attack', 'game', 'variation', 'system', 'the', 'a', 'an', 'for', 'by', 'in', 'on', 'white', 'black', 'both', 'old', 'new'}
    
    filter_parts = []
    for part in f_lower.split():
        subparts = part.split('-')
        for subpart in subparts:
            if subpart not in ignore_words and len(subpart) > 2:
                filter_parts.append(normalize_word(subpart))
    
    opening_parts = []
    for part in opening_lower.split():
        subparts = part.split('-')
        for subpart in subparts:
            if subpart not in ignore_words and len(subpart) > 2:
                opening_parts.append(normalize_word(subpart))
    
    print(f'  Filter parts (normalized): {filter_parts}')
    print(f'  Opening parts (normalized): {opening_parts}')
    
    has_match = any(fp in opening_parts for fp in filter_parts)
    print(f'  Has shared concept: {has_match}')
    print()


