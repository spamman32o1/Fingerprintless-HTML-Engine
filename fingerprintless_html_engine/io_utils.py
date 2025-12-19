from __future__ import annotations

import os
from pathlib import Path

from .constants import FALLBACK_ENCODINGS


def prompt_int(msg: str, lo: int = 1) -> int:
    while True:
        s = input(msg).strip()
        try:
            n = int(s)
        except ValueError:
            print("Please enter an integer.")
            continue
        if n < lo:
            print(f"Must be >= {lo}.")
            continue
        return n


def _prompt_yes_no(message: str, default: bool) -> bool:
    while True:
        choice = input(message).strip().lower()
        if choice == "":
            return default
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _clean_path_text(text: str) -> str:
    return text.strip().strip('"').strip("'")


def _parse_input_paths(raw_input: str) -> list[Path]:
    cleaned = _clean_path_text(raw_input)
    if not cleaned:
        return []
    parts = [_clean_path_text(part) for part in cleaned.split(",")]
    return [Path(part) for part in parts if part]


def _pick_windows_files() -> list[Path]:
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    paths = filedialog.askopenfilenames(
        title="Select HTML files",
        filetypes=[("HTML files", "*.html;*.htm"), ("All files", "*.*")],
    )
    root.destroy()
    return [Path(path) for path in paths]


def _flush_windows_stdin() -> None:
    if os.name != "nt":
        return
    try:
        import msvcrt
    except ImportError:
        return
    while msvcrt.kbhit():
        msvcrt.getwch()


def _collect_input_files() -> list[Path]:
    while True:
        if os.name == "nt":
            raw = input(
                "Input HTML file path(s) (comma-separated, blank to choose in File Explorer): "
            )
            raw = raw.strip()
            if not raw:
                paths = _pick_windows_files()
                _flush_windows_stdin()
            else:
                paths = _parse_input_paths(raw)
        else:
            raw = input("Input HTML file path(s) (comma-separated): ")
            paths = _parse_input_paths(raw)

        if not paths:
            print("No files provided. Please try again.")
            continue

        missing = [path for path in paths if not path.exists() or not path.is_file()]
        if missing:
            print("These paths were not found or are not files:")
            for path in missing:
                print(f"  - {path}")
            continue

        return paths


def read_text_with_fallback(path: Path, encoding: str) -> str:
    try:
        return path.read_text(encoding=encoding)
    except UnicodeError as exc:
        for fallback in FALLBACK_ENCODINGS:
            if fallback.lower() == encoding.lower():
                continue
            try:
                print(f"Decode error with '{encoding}'. Retrying with '{fallback}'.")
                return path.read_text(encoding=fallback)
            except UnicodeError:
                continue
        raise SystemExit(
            f"Could not decode '{path}' with '{encoding}' or fallbacks "
            f"{', '.join(FALLBACK_ENCODINGS)}."
        ) from exc


__all__ = [
    "_collect_input_files",
    "_prompt_yes_no",
    "prompt_int",
    "read_text_with_fallback",
]
