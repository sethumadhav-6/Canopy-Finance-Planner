"""Reusable glassmorphic building blocks: gradient app background + frosted card container."""
from __future__ import annotations

from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget

from ui import theme


class GradientBackground(Widget):
    """Full-screen dark multi-stop gradient backdrop, with soft gold glow accents, that
    glass cards float above."""

    stops = ListProperty(theme.BG_STOPS)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _lerp_stop(self, t: float):
        """t in [0,1] across the full stop list, piecewise-linear interpolated."""
        stops = self.stops
        n = len(stops) - 1
        if n <= 0:
            return stops[0]
        seg = min(int(t * n), n - 1)
        local_t = (t * n) - seg
        a, b = stops[seg], stops[seg + 1]
        return tuple(a[i] + (b[i] - a[i]) * local_t for i in range(4))

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        steps = 32
        with self.canvas:
            for i in range(steps):
                t = i / (steps - 1)
                r, g, b, a = self._lerp_stop(t)
                Color(r, g, b, a if a else 1)
                band_h = self.height / steps
                Rectangle(
                    pos=(self.x, self.y + self.height - band_h * (i + 1)),
                    size=(self.width, band_h + 1),
                )
            # Soft warm glow, upper-right -- a large low-alpha circle standing in for a blur.
            Color(*theme.GLOW_COLOR)
            glow_r = self.width * 0.9
            Ellipse(pos=(self.x + self.width * 0.35, self.y + self.height * 0.78 - glow_r / 2),
                     size=(glow_r, glow_r))
            Color(theme.EMERALD[0], theme.EMERALD[1], theme.EMERALD[2], 0.05)
            glow_r2 = self.width * 0.8
            Ellipse(pos=(self.x - self.width * 0.25, self.y - glow_r2 * 0.15),
                     size=(glow_r2, glow_r2))


class GlassCard(BoxLayout):
    """Frosted-glass panel: translucent rounded rect + subtle border, used everywhere in the UI."""

    radius = NumericProperty(theme.CARD_RADIUS)
    fill_color = ListProperty(theme.GLASS_FILL)
    border_color = ListProperty(theme.GLASS_BORDER)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.padding = kwargs.get("padding", theme.PADDING)
        self.spacing = kwargs.get("spacing", theme.SPACING)
        with self.canvas.before:
            # Faint drop-shadow illusion: a slightly larger, darker, offset rounded rect
            # behind the card fill -- cheap depth cue without a real blur pass.
            self._shadow_c = Color(0, 0, 0, 0.18)
            self._shadow = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._fill = Color(*self.fill_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._border_c = Color(*self.border_color)
            self._border = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius), width=1.1)
        self.bind(pos=self._redraw, size=self._redraw, fill_color=self._redraw, border_color=self._redraw)

    def _redraw(self, *_):
        shadow_off = 3
        self._shadow.pos = (self.x, self.y - shadow_off)
        self._shadow.size = self.size
        self._shadow.radius = [self.radius]
        self._fill.rgba = self.fill_color
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [self.radius]
        self._border_c.rgba = self.border_color
        self._border.rounded_rectangle = (self.x, self.y, self.width, self.height, self.radius)


class GradientCard(BoxLayout):
    """
    Warm gold-gradient panel used for headline/CTA emphasis (the dashboard spend
    total, primary summary numbers) -- distinct from the neutral GlassCard so the
    one or two most important numbers on a screen stand out.
    """

    radius = NumericProperty(theme.CARD_RADIUS)
    start_color = ListProperty(theme.ACCENT_GOLD_LIGHT)
    end_color = ListProperty(theme.ACCENT_GOLD_DARK)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.padding = kwargs.get("padding", theme.PADDING)
        self.spacing = kwargs.get("spacing", theme.SPACING)
        with self.canvas.before:
            self._shadow_c = Color(*theme.ACCENT_SOFT)
            self._shadow = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
        self._bands: list[tuple] = []
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_):
        self.canvas.before.clear()
        if self.width <= 0 or self.height <= 0:
            return
        shadow_off = 5
        with self.canvas.before:
            Color(*theme.ACCENT_SOFT)
            RoundedRectangle(pos=(self.x, self.y - shadow_off), size=self.size, radius=[self.radius])
            steps = 20
            for i in range(steps):
                t = i / (steps - 1)
                r = self.start_color[0] + (self.end_color[0] - self.start_color[0]) * t
                g = self.start_color[1] + (self.end_color[1] - self.start_color[1]) * t
                b = self.start_color[2] + (self.end_color[2] - self.start_color[2]) * t
                Color(r, g, b, 1)
                band_w = self.width / steps
                RoundedRectangle(
                    pos=(self.x + band_w * i, self.y), size=(band_w + 1, self.height),
                    radius=[self.radius if i in (0, steps - 1) else 0],
                )
            Color(1, 1, 1, 0.25)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius), width=1.1)
