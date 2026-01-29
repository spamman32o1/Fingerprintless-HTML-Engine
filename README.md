# ⚡ Fingerprintless HTML Engine

## ✨ Purpose
Turn a single HTML file into multiple **stealthy**, **high-fidelity**, and **natural-looking** variants designed to reduce fingerprinting patterns while preserving content.

## 🚀 Features
- 🧬 **Adaptive Variant Generation**: Produces multiple randomized HTML outputs while preserving layout semantics and content intent.
- 🎯 **Precision Text Mutation**: Wraps inline text in randomized spans and injects subtle styling shifts without changing meaning.
- 🧱 **Robust Structure Shuffling**: Reorders safe wrapper elements and nesting depth to deliver **distinct** yet **valid** markup.
- 🎨 **Dynamic Styling Noise**: Applies realistic typography, spacing, layout, and color perturbations for **lifelike** rendering diversity.
- 🧩 **Table Attribute Normalization**: Converts legacy table attributes (`cellspacing`, `cellpadding`, `align`, `border`) into clean modern CSS.
- 🛰️ **JSON-LD Decoys**: Inserts guarded, size-limited JSON-LD snippets to blend with real-world document patterns.
- 🕵️ **IE Conditional Noise**: Adds conditional comment blocks to mimic historical email/client HTML quirks.
- 🧪 **Synonym Swaps**: Optionally applies synonym maps to create **subtle** textual variance in safe contexts.
- 🧼 **Sanitization & Minification**: Normalizes input HTML and outputs compressed, efficient variants for lightweight delivery.
- 🎲 **Natural Randomization**: Fresh entropy per run ensures every output stays uniquely varied.
- 🧾 **Metanoise Layering**: Injects randomized `<meta>` blocks (`name`, `property`, `http-equiv`) to simulate organic metadata footprints.
- 🧷 **Attribute Texture**: Varies attribute ordering, casing, and spacing to avoid deterministic fingerprints.
- 🧭 **Head & Body Balancing**: Distributes noise across head and body so outputs look hand-authored instead of machine-generated.
- 🧯 **Safety-First Mutations**: Avoids destructive transformations to keep HTML valid and rendering stable.

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
- Strict mode prompt: You will be asked whether to enable strict mode (and optionally super strict mode) after selecting the variant count.

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
Enable strict mode (inline styles, no style blocks)? y/n (default n):
Enable super strict mode for aggressive providers? y/n (default n):
Optional synonym map file path (pipe-separated synonyms per line, blank to skip):
```

## ✅ Strict Mode (Docomo-Friendly)
Enable strict mode when prompted (`y`) to generate variants optimized for stricter Japanese
mobile clients where CSS support is limited (e.g., Docomo). Compared to the default
Gmail-friendly output, strict mode disables or avoids:

- **`<style>` blocks**: all styling moves inline on `body`, wrapper, and content elements.
- **`@media` rules**: responsive media queries are skipped (no stylesheet means no media queries).
- **Class-based styling**: wrapper/content classes and class selectors are not used.
- **Flex/grid layouts**: strict mode sticks to block/flow-root layout patterns only.
- **`max-width` and rounded corners**: avoids `max-width` and `border-radius` in wrapper and button styles.
- **Span-based text wrapping**: inline text span jittering is disabled (plain text kept).
- **Noise divs + IE comments**: HTML noise wrappers and IE conditional comment noise are removed.
- **Meta noise**: randomized meta tag injection is skipped in the `<head>`.
- **Content box wrappers**: extra wrapper boxes around content sections are skipped.
- **Table/list normalization only**: table/list attributes are normalized with inline styles for compatibility.

## 🧱 Super Strict Mode (Aggressive Providers)
If you answer `y` to the follow-up prompt, the engine will switch to **super strict** mode
for aggressive providers (e.g., libero.it) that may strip modern CSS or wrappers. Super strict
mode builds on strict mode by further minimizing styling and layout variability:

- **No noise or JSON-LD decoys**: skips metanoise, JSON-LD scripts, IE comments, and noise divs.
- **Conservative layout**: always uses the table fallback layout path with minimal wrapper layers.
- **Minimal span injection**: text span wrapping and extra inline styles are kept to a minimum.
- **Reduced CSS complexity**: avoids gradients, background images, and opacity tweaks.

## 🧾 Metanoise
Every generated variant (except strict mode) automatically receives a **metanoise** block that simulates the messy metadata you see in real-world documents. The engine:

- Picks a mix of `name`, `property`, and `http-equiv` tags from diverse categories (SEO, social, caching, mobile, privacy) to keep headers varied.
- Randomizes attribute casing, whitespace, separators, and occasionally prefixes values with unique identifiers for organic entropy.
- Avoids obvious duplication while still allowing selective repeats so the head looks hand-authored rather than machine-perfect.

This head-level noise strengthens the variants’ ability to evade fingerprinting while remaining standards-compliant and harmless to content rendering.

## 📦 Requirements
- Python 3.10+
- No external dependencies

## 🌟 Why It Shines
Fingerprintless HTML Engine is engineered for **aggressive uniqueness** without sacrificing **rendering fidelity**. It’s a **powerful**, **surgical**, and **battle-tested** way to introduce safe entropy into HTML.
