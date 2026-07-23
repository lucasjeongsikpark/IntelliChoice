"""WCAG contrast checker for packages/ui-brand/tokens.css.

Asserts every real text/background token pair used for text meets the
4.5:1 WCAG AA threshold, in both the light (`:root`) and dark
(`@media (prefers-color-scheme: dark)`) blocks. Deliberately does not check
the raw --brand-* tier (D-067) — those tokens are only ever used
non-textually (logo, gradient highlights).

Usage: uv run python packages/ui-brand/check_contrast.py
   or: python3 packages/ui-brand/check_contrast.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOKENS_PATH = Path(__file__).parent / "tokens.css"

# (foreground token, background token, human label) — the real text/bg pairs
# this app surface renders. Kept in sync by hand with tokens.css and the
# App.css files that consume these tokens.
PAIRS: list[tuple[str, str, str]] = [
    ("--text", "--bg", "body text on page background"),
    ("--text", "--panel-bg", "body text on panel background"),
    ("--text-h", "--bg", "heading text on page background"),
    ("--text-h", "--panel-bg", "heading text on panel background"),
    ("--accent", "--bg", "link/accent text on page background"),
    ("--accent", "--panel-bg", "link/accent text on panel background"),
    ("--accent-contrast", "--accent", "button text on solid accent button"),
    ("--pink-interactive", "--bg", "pink interactive text on page background"),
    ("--pink-interactive", "--panel-bg", "pink interactive text on panel background"),
    ("--error", "--bg", "error text on page background"),
    ("--error", "--panel-bg", "error text on panel background"),
    ("--success", "--bg", "success text on page background"),
    ("--success", "--panel-bg", "success text on panel background"),
    ("--footer-text", "--footer-bg", "footer text on footer background"),
    ("--footer-link", "--footer-bg", "footer link on footer background"),
]

MIN_RATIO = 4.5

HEX_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;")


def parse_blocks(css: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return (light_tokens, dark_tokens). Dark inherits any token light
    defines and doesn't override (matches how the CSS cascade actually
    resolves this file at runtime)."""
    dark_split = css.split("@media (prefers-color-scheme: dark)")
    light_css = dark_split[0]
    dark_css = dark_split[1] if len(dark_split) > 1 else ""

    light = dict(HEX_RE.findall(light_css))
    dark_overrides = dict(HEX_RE.findall(dark_css))
    dark = {**light, **dark_overrides}
    return light, dark


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        c_srgb = c / 255
        return c_srgb / 12.92 if c_srgb <= 0.03928 else ((c_srgb + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a = relative_luminance(hex_to_rgb(hex_a))
    lum_b = relative_luminance(hex_to_rgb(hex_b))
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def check_scheme(name: str, tokens: dict[str, str]) -> bool:
    print(f"\n{name} scheme:")
    all_ok = True
    for fg, bg, label in PAIRS:
        if fg not in tokens or bg not in tokens:
            print(f"  SKIP  {label} — {fg} or {bg} not defined in this scheme")
            continue
        ratio = contrast_ratio(tokens[fg], tokens[bg])
        ok = ratio >= MIN_RATIO
        all_ok &= ok
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {label}: {tokens[fg]} on {tokens[bg]} = {ratio:.2f}:1")
    return all_ok


def main() -> int:
    css = TOKENS_PATH.read_text()
    light, dark = parse_blocks(css)
    light_ok = check_scheme("light", light)
    dark_ok = check_scheme("dark", dark)
    if light_ok and dark_ok:
        print("\nAll checked pairs pass WCAG AA (>= 4.5:1).")
        return 0
    print("\nOne or more pairs fail WCAG AA (>= 4.5:1).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
