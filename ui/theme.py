"""
Glassmorphic theme constants for Canopy Finance Planner.

v2: a "classy" dark navy/charcoal backdrop with a warm gold accent (evokes a
premium banking app rather than a generic purple Material app) instead of the
flatter indigo/teal used in the first pass. Kivy/KivyMD can't do a true OS-level
background blur on Android, so "glass" is approximated the standard mobile-UI
way: semi-transparent panels with soft rounded corners, a subtle light border,
and a layered gradient backdrop behind them so the translucency reads as glass.
"""
from __future__ import annotations

from kivy.utils import get_color_from_hex as hex_color

# Backdrop gradient: near-black navy -> deep indigo-blue -> dusk blue, three
# stops instead of two so the gradient has more depth/movement on a tall screen.
BG_STOPS = [hex_color("#0A0D16"), hex_color("#141A30"), hex_color("#1E2A4A")]
BG_TOP = BG_STOPS[0]
BG_BOTTOM = BG_STOPS[-1]

# Soft warm glow color, layered behind headline/CTA cards for a subtle premium
# highlight (rendered as large low-alpha circles, not a real blur).
GLOW_COLOR = (0.91, 0.75, 0.42, 0.16)

# Glass panel: low-alpha white over the dark backdrop reads as frosted glass.
GLASS_FILL = (1, 1, 1, 0.07)
GLASS_FILL_ELEVATED = (1, 1, 1, 0.115)
GLASS_BORDER = (1, 1, 1, 0.20)

TEXT_PRIMARY = hex_color("#F6F3EA")
TEXT_SECONDARY = (1, 1, 1, 0.66)
TEXT_MUTED = (1, 1, 1, 0.44)

# For text sitting on top of the gold GradientCard -- dark, warm-toned so it
# reads as ink-on-gold rather than reusing the light on-dark palette above.
TEXT_ON_GOLD = hex_color("#241A08")
TEXT_ON_GOLD_SOFT = (0.14, 0.10, 0.03, 0.72)

# Warm gold accent (replaces the earlier flat indigo accent) -- a two-stop
# gradient used for CTA cards/buttons/progress fills to read as "premium"
# rather than flat-filled.
ACCENT_GOLD_LIGHT = hex_color("#F0D48A")
ACCENT_GOLD_DARK = hex_color("#C9962F")
ACCENT = ACCENT_GOLD_DARK           # kept as the single-color fallback used across the app
ACCENT_SOFT = (0.82, 0.69, 0.33, 0.22)

EMERALD = hex_color("#3FBF8F")       # positive / income / under-budget
SUCCESS = EMERALD
WARNING = hex_color("#E8B84B")
DANGER = hex_color("#E8637A")

CARD_RADIUS = 22
CHIP_RADIUS = 14
SPACING = 12
PADDING = 16

FONT_SIZE_H1 = "24sp"
FONT_SIZE_H2 = "18sp"
FONT_SIZE_BODY = "14sp"
FONT_SIZE_CAPTION = "12sp"


def category_color(hex_str: str, alpha: float = 1.0):
    r, g, b, _ = hex_color(hex_str or "#C9962F")
    return (r, g, b, alpha)


def status_color(pct_used: float):
    """Emerald under 80%, gold 80-100%, coral over budget -- used across envelopes/budget UI."""
    if pct_used >= 100:
        return DANGER
    if pct_used >= 80:
        return WARNING
    return SUCCESS


def gradient_stop(t: float):
    """Interpolate the accent gold gradient at t in [0, 1] -- light gold to deep gold."""
    r = ACCENT_GOLD_LIGHT[0] + (ACCENT_GOLD_DARK[0] - ACCENT_GOLD_LIGHT[0]) * t
    g = ACCENT_GOLD_LIGHT[1] + (ACCENT_GOLD_DARK[1] - ACCENT_GOLD_LIGHT[1]) * t
    b = ACCENT_GOLD_LIGHT[2] + (ACCENT_GOLD_DARK[2] - ACCENT_GOLD_LIGHT[2]) * t
    return (r, g, b, 1)
