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
- 🧾 **Metanoise Layering**: Injects realistic, randomized `<meta>` blocks (including `name`, `property`, and `http-equiv`) to mimic organic metadata footprints.

## 🛠️ Usage
1. Run the script:
   ```bash
   ./script.py
   ```
2. Provide the input HTML file path.
3. Choose how many variants to generate.
4. (Optional) Supply a synonym map file with `wordA | wordB | wordC` lines.

The script outputs a timestamped `variants_YYYYMMDD_HHMMSS` directory filled with variant HTML files.

### 🧭 CLI Options
Run `./script.py --help` to see all flags. Common switches include:

- `--encoding`: Set input HTML encoding (default `utf-8`, with fallbacks to `latin-1` and `windows-1252`).
- `--no-ie-conditional-comments`: Disable randomized IE conditional comment blocks.
- `--no-structure-randomize`: Disable wrapper structure shuffling.
- `--max-nesting`: Override maximum wrapper nesting depth.
- `--max-nesting-jitter`: Apply random +/- jitter to the max nesting depth per variant.

### 📂 Multiple Inputs
If you supply multiple input files, the engine will prompt to place outputs in a shared
`variants_YYYYMMDD_HHMMSS` folder (with filename prefixes), or in distinct folders per input.

### 🧪 Example
```bash
./script.py --max-nesting 6 --max-nesting-jitter 2
```
```text
Enter HTML file path: samples/page.html
How many variants? 5
Optional synonym map file path (pipe-separated synonyms per line, blank to skip):
```

## 🧾 Metanoise
Every generated variant automatically receives a **metanoise** block that simulates the messy metadata you see in real-world documents. The engine:

- Picks a mix of `name`, `property`, and `http-equiv` tags from diverse categories (SEO, social, caching, mobile, privacy) to keep headers varied.
- Randomizes attribute casing, whitespace, separators, and occasionally prefixes values with unique identifiers for organic entropy.
- Avoids obvious duplication while still allowing selective repeats so the head looks hand-authored rather than machine-perfect.

This head-level noise strengthens the variants’ ability to evade fingerprinting while remaining standards-compliant and harmless to content rendering.

## 📦 Requirements
- Python 3.10+
- No external dependencies

## 🌟 Why It Shines
Fingerprintless HTML Engine is engineered for **aggressive uniqueness** without sacrificing **rendering fidelity**. It’s a **powerful**, **surgical**, and **battle-tested** way to introduce safe entropy into HTML.
