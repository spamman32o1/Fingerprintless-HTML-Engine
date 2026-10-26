# ⚡ Fingerprintless HTML Engine

Takes one HTML file and produces multiple variants that render the same but differ
in markup, so generated emails don't share a fixed fingerprint.

Every visual change is derived from the input. The engine reads the source's own
colors, fonts, spacing and background, then jitters them within a small bounded
range. It does not pick from a fixed palette, so a near-black heading stays
near-black instead of turning grey.

## Requirements

- Python 3.10+
- No Python dependencies are required to generate variants

Optional components:

| Purpose | Requirement |
|---|---|
| Synonym swaps | [Ollama](https://ollama.com) daemon (see below) |
| Unique image payloads | [Pillow](https://python-pillow.org) — `pip install pillow` |

Pillow is only needed for image pixel jitter. Without it, images are still
inlined, just byte-identical across variants.

## Usage

```bash
./script.py
```

There are no positional arguments — everything is prompt-driven:

1. **Input file path(s)** — comma-separated for multiple files.
2. **How many variants?**
3. **Optional synonym map file path** — blank to skip.
4. **Output mode** — `1) default  2) strict  3) super strict  4) libero`.

Output goes to `variants_YYYYMMDD_HHMMSS/` as `<input>_variant_001.html`,
`<input>_variant_002.html`, … With multiple inputs you're asked whether to share one
folder (files get a numbered `<name>_` prefix) or use one folder per input.

Uniqueness is enforced per batch: if a generated document is byte-identical to an
earlier one it is regenerated, up to 32 attempts.

## Output modes

| Mode | Styles | Use for |
|---|---|---|
| `default` | `<style>` block, media queries, classes | Gmail and other modern clients |
| `strict` | No `<style>` block and no media queries; styling moves inline. Generated classes may still appear, but nothing depends on them | Clients that strip `<head>` CSS |
| `super_strict` | As strict, plus no wrapper nesting, no IE comments, layout table pinned to the inner slot | Aggressive clients that strip modern CSS |
| `libero` | `super_strict` rendering, output quoted-printable encoded, `lang` defaults to `it` | libero.it |

In every strict mode span wrapping is disabled and text stays plain.

Gradients and noise textures are a separate concern: they are only ever applied
when the source document has no styles of its own, and `--no-gradients` /
`--no-noise-textures` turn them off outright.

## Synonym generation (local LLM)

Text variation is produced by a small local model served by
[Ollama](https://ollama.com). Start the server once:

```bash
docker compose up -d ollama
docker compose run --rm ollama-pull   # pulls qwen2.5:3b (~1.9 GB)
```

The engine talks to `http://127.0.0.1:11434`. Default model is `qwen2.5:3b`.

`qwen2.5:3b` is the intended model. The smaller qwen2.5 variants (1.5b, 0.5b) fail
validation: they emit multi-word spans where a single word was requested, or map a
word to itself, so their output is rejected. For a different model, size upward
(`qwen2.5:7b`) rather than downward.

How it works:

- The model receives the document's **visible prose**, not raw HTML. Base64 data
  URIs, `<style>`/`<script>` bodies, attribute values, tags and entities are
  stripped first, so it reads sentences.
- It returns swaps, which are **validated against the source** before use: the
  original must actually appear in the prose, alternatives must be plain words and
  never collide with another group's original, and nested spans keep the longest
  one (`has been released` wins over `released`, so nothing is rewritten twice).
- Single words **and phrases up to three words** are supported — swapping a phrase
  is often the only way to keep the context intact.
- One request per document, cached in-process. Cost does not scale with variant
  count.

Override with `--synonym-model` / `--ollama-host`, or `OLLAMA_MODEL` /
`OLLAMA_HOST`. If the daemon is down or the model isn't pulled, the run stops
before writing anything and prints the command to fix it. Use
`--no-generate-synonyms` to skip swaps, or pass your own map file.

Generated groups are written to `generated_synonym_map.txt` in the output folder
(pipe-delimited, reusable via the map-file prompt). Disable with
`--no-write-generated-synonym-map`.

## What gets varied

All of it is source-relative and bounded:

- **Colors** — background, text, borders and accents jittered around the original
  values. Text/background pairs are held to a 4.5 contrast ratio and accents to 3.0
  (WCAG AA), so a near-black heading stays near-black on white.
- **Gradients and noise textures** — derived from the source colors rather than
  fixed presets.
- **Typography** — font stack, size, spacing, line height and advanced features
  (variation settings, optical sizing, kerning).
- **Structure** — safe wrapper nesting, layout-table placement and content-box
  wrapping.
- **Attributes** — ordering, casing and spacing, so the markup isn't byte-identical.
- **Text** — span wrapping and word-level chunking, plus the synonym swaps above.
- **Tables** — legacy `cellspacing`, `cellpadding`, `align` and `border` attributes
  normalized to inline CSS.
- **Images** — remote references inlined as data URLs, then re-encoded with
  imperceptible pixel noise so every payload is a distinct base64 string.

IE conditional comments are opt-in and **off by default** (`--ie-conditional-comments`).

## Image pixel jitter

Each `<img src>` and CSS `url(data:…)` is decoded, altered so it is unchanged to
the eye, and re-encoded. Every occurrence is handled separately, so two copies of
the same image in one variant get two different payloads.

| Source format | Treatment | Visible change |
|---|---|---|
| PNG, BMP | One random colour channel of one visible pixel moved by ±1 | max 1/255 |
| Lossless WebP | As PNG; re-encoded losslessly | max 1/255 |
| JPEG | Sparse speckle (2% of pixels, ±3) at the source's own quality tables | mean diff ≈ 0.03/255 |
| GIF, lossy WebP, SVG, AVIF | Left byte-identical | none |

Relevant constraints:

- JPEG is written as 4:4:4, because 4:2:0 chroma averaging erases a pixel-level
  change. This costs roughly 2% more bytes.
- A JPEG whose re-encode would shift mean brightness by more than 2/255 (already
  heavily compressed sources) is left byte-identical rather than degraded.
- Payloads above 12 MB are not decoded.
- A fully transparent PNG has no pixel to change and passes through.
- Lossy WebP is skipped because Pillow's decoder cannot re-save it without a
  quality loss that changes the whole image.

Disable with `--no-image-pixel-jitter`.

## CLI flags

Every transformation is on by default; the flags disable it.

```
--encoding ENCODING              Input encoding (default utf-8; falls back to
                                 latin-1, then windows-1252)
--ie-conditional-comments        Opt into IE conditional comment noise
--no-ie-conditional-comments     Disable it (default)
--no-structure-randomize         Disable wrapper structure randomization
--max-nesting N                  Base max wrapper nesting (default 4)
--max-nesting-jitter N           Random +/- jitter applied per variant (default 0)
--no-dark-mode                   Disable dark theme styling
--no-css-randomization           Disable CSS value and typography jitter
--no-font-randomization          Disable fallback font-stack selection
--no-font-css                    Disable typography CSS
--no-font-features               Disable advanced font features
--no-gradients                   Disable gradient backgrounds
--no-noise-textures              Disable noise texture overlays
--no-color-palette-randomization Preserve original colors
--no-span-wrap                   Disable span wrapping
--no-wrapper-nesting             Disable wrapper nesting
--no-layout-randomization        Disable layout table randomization
--no-layout-tables               Force a plain layout container
--no-wrapper-styles              Disable wrapper padding/margin/border/shadow
--no-body-styles                 Disable body-level styling
--no-image-inlining              Don't inline remote images as data URLs
--no-remote-image-cache          Don't reuse downloaded images within a run
--no-image-pixel-jitter          Don't alter image pixels (payloads may repeat)
--pretty-output                  Pretty-print with indentation
--no-pretty-output               Disable pretty-print (on by default in libero)
--generate-synonyms              Enable synonym generation (default)
--no-generate-synonyms           Disable it
--ollama-host URL                Ollama endpoint (default $OLLAMA_HOST or
                                 http://127.0.0.1:11434)
--synonym-model NAME             Model (default qwen2.5:3b)
--write-generated-synonym-map    Write the map to disk
--no-write-generated-synonym-map Don't write it
--generated-synonym-map-filename Name of the map file
```

When jitter is enabled the remote-image cache is per variant, because a shared
cache would hand every variant the same stored payload. Each variant downloads
its images once.

## Example

```bash
./script.py --max-nesting 6 --max-nesting-jitter 2
```

```text
Input HTML file path(s) (comma-separated): samples/page.html
How many variants? 5
Optional synonym map file path (... blank to skip):
Select output mode:
  1) default
  2) strict
  3) super strict
  4) libero
Choose mode [1-4] (default 1):
```

Then a map file and one HTML file per variant:

```text
variants_20261025_204508/
├── generated_synonym_map.txt
├── page_variant_001.html
└── page_variant_002.html
```

## Repo layout

| Path | Purpose |
|---|---|
| `script.py` | Entry point |
| `fingerprintless_html_engine/cli.py` | Prompts, flags, orchestration, prose extraction |
| `fingerprintless_html_engine/variant.py` | Per-variant assembly |
| `fingerprintless_html_engine/css_utils.py` | Source-relative CSS and color jitter |
| `fingerprintless_html_engine/synonym_discovery.py` | Ollama client and output validation |
| `fingerprintless_html_engine/text_utils.py` | Span wrapping and synonym application |
| `fingerprintless_html_engine/structure_utils.py` | Wrapper and layout randomization |
| `fingerprintless_html_engine/image_utils.py` | Data-URI inlining, cache, pixel jitter |
| `fingerprintless_html_engine/noise_utils.py` | IE conditional comments |
| `docker-compose.yml` | Ollama service; model volume pinned as `fl-ollama-models` |

## Notes

- `variants_*/` output and `__pycache__/` are gitignored.
- The Ollama volume is named explicitly so `docker compose down` doesn't discard
  the ~1.9 GB model.
- If a separate Ollama container already holds port 11434, stop it before
  `docker compose up -d ollama`.
