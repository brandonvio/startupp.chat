#!/usr/bin/env python3

# Test grapheme counting for the Bluesky post

text = """Just watched MIT's deep‑learning masterclass by Prof. Andrew Ng (video ID: O5xeyoRL95U). Great overview of neural nets, CNNs, RNNs, GA... https://youtu.be/O5xeyoRL95U

#DeepLearning #MIT #AI #NeuralNetworks #MachineLearning #ReinforcementLearning #GAN #AutoML #NLP #AIethics #NeuralArchitectureSearch"""

print(f"Text: {repr(text)}")
print(f"Length (characters): {len(text)}")

# Test different grapheme counting methods
try:
    import grapheme
    grapheme_count = grapheme.length(text)
    print(f"Graphemes (grapheme library): {grapheme_count}")
except ImportError:
    print("Grapheme library not available")

# Fallback method
import unicodedata
normalized = unicodedata.normalize('NFC', text)
print(f"Normalized length: {len(normalized)}")

# Check for special characters
special_chars = []
for i, char in enumerate(text):
    if ord(char) > 127:  # Non-ASCII
        special_chars.append((i, char, ord(char), unicodedata.name(char, 'UNKNOWN')))

print(f"\nSpecial characters found: {len(special_chars)}")
for pos, char, code, name in special_chars[:10]:  # Show first 10
    print(f"  Position {pos}: '{char}' (U+{code:04X}) - {name}")

# Test truncation
if len(text) > 299:
    truncated = text[:296] + "..."
    print(f"\nTruncated text ({len(truncated)} chars): {truncated}")