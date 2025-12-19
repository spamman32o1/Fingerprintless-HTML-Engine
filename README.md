# ⚡ Fingerprintless HTML Engine

## ✨ Purpose
Turn a single HTML file into multiple **stealthy**, **high-fidelity**, and **natural-looking** variants designed to reduce fingerprinting patterns while preserving content.

## 🚀 Features
- 🧬 **Adaptive Variant Generation**: Creates multiple randomized HTML outputs with consistent structure and content integrity.
- 🎯 **Precision Text Mutation**: Carefully wraps text in randomized spans and safely injects subtle layout changes without altering meaning.
- 🧱 **Robust Structure Shuffling**: Shifts safe wrapper elements and nesting to produce **distinct** yet **valid** markup.
- 🎨 **Dynamic Styling Noise**: Injects randomized typography, spacing, layout, and color choices for **lifelike** rendering diversity.
- 🧩 **Table Attribute Normalization**: Converts legacy table attributes (cellspacing, cellpadding, align, border) into modern CSS for cleaner output.
- 🛰️ **JSON-LD Decoys**: Inserts guarded, size-limited JSON-LD snippets to blend with real-world HTML patterns.
- 🕵️ **IE Conditional Noise**: Adds conditional comment blocks to mimic historical email/client HTML quirks.
- 🧪 **Synonym Swaps**: Optionally applies synonym maps to create **subtle** textual variance.
- 🧼 **Sanitization & Minification**: Normalizes input HTML and outputs compressed, efficient variants.
- 🎲 **Natural Randomization**: Each run uses fresh randomness to keep every output uniquely varied.

## 🛠️ Usage
1. Run the script:
   ```bash
   ./script.py
   ```
2. Provide the input HTML file path.
3. Choose how many variants to generate.
4. (Optional) Supply a synonym map file with `wordA | wordB | wordC` lines.

The script outputs a timestamped `variants_YYYYMMDD_HHMMSS` directory filled with variant HTML files.

## 📦 Requirements
- Python 3.10+
- No external dependencies

## 🌟 Why It Shines
Fingerprintless HTML Engine is engineered for **aggressive uniqueness** without sacrificing **rendering fidelity**. It’s a **powerful**, **surgical**, and **battle-tested** way to introduce safe entropy into HTML.
