"""
Lightweight, dependency-free chart widgets drawn with Kivy canvas instructions.

Deliberately avoids matplotlib/kivy-garden.graph: those add heavy, sometimes
buildozer-incompatible native deps. Pure-canvas charts stay small, render fast,
and package reliably into an APK.
"""
from __future__ import annotations

from kivy.graphics import Color, Line, Mesh, RoundedRectangle
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.widget import Widget
from kivy.uix.label import Label

from ui import theme


class TrendLineChart(Widget):
    """Month-over-month spend trend: filled line chart with dot markers and value labels."""

    points_data = ListProperty([])  # list of {"label": str, "value": float}
    line_color = ListProperty(theme.ACCENT)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, points_data=self._redraw)
        self._labels: list[Label] = []

    def _redraw(self, *_):
        self.canvas.clear()
        for lbl in self._labels:
            if lbl.parent:
                self.remove_widget(lbl)
        self._labels.clear()

        data = self.points_data
        if not data or self.width <= 0 or self.height <= 0:
            return

        pad_left, pad_right = 12, 12
        pad_top, pad_bottom = 16, 28
        plot_w = self.width - pad_left - pad_right
        plot_h = self.height - pad_top - pad_bottom
        values = [d["value"] for d in data]
        max_v = max(values) if max(values) > 0 else 1
        n = len(data)
        step_x = plot_w / max(n - 1, 1)

        coords = []
        for i, d in enumerate(data):
            x = self.x + pad_left + step_x * i
            y = self.y + pad_bottom + (d["value"] / max_v) * plot_h
            coords.append((x, y))

        with self.canvas:
            # filled area under the line
            Color(*theme.ACCENT_SOFT)
            fill_points = [coords[0][0], self.y + pad_bottom]
            for x, y in coords:
                fill_points += [x, y]
            fill_points += [coords[-1][0], self.y + pad_bottom]
            try:
                # Tesselator lives in a separate optional module and needs Kivy's C
                # tess extension to be compiled in -- not guaranteed on every build/
                # platform, so both the import and the use are guarded here. When
                # unavailable, the line + dot markers below still convey the trend.
                from kivy.graphics.tesselator import Tesselator
                tess = Tesselator()
                tess.add_contour(fill_points)
                tess.tesselate()
                for vertices, indices in tess.meshes:
                    self.canvas.add(Mesh(vertices=vertices, indices=indices, mode="triangle_fan"))
            except Exception:
                pass

            Color(*self.line_color)
            flat = [c for xy in coords for c in xy]
            Line(points=flat, width=2.2, joint="round")
            for x, y in coords:
                Line(circle=(x, y, 4), width=2)

        for i, d in enumerate(data):
            x, y = coords[i]
            lbl = Label(
                text=d["label"], font_size=theme.FONT_SIZE_CAPTION, color=theme.TEXT_SECONDARY,
                size_hint=(None, None), size=(60, 16), pos=(x - 30, self.y),
            )
            self.add_widget(lbl)
            self._labels.append(lbl)
            val_lbl = Label(
                text=f"{d['value']:.0f}", font_size=theme.FONT_SIZE_CAPTION, color=theme.TEXT_PRIMARY,
                size_hint=(None, None), size=(70, 16), pos=(x - 35, y + 6),
            )
            self.add_widget(val_lbl)
            self._labels.append(val_lbl)


class CategoryBarRow(Widget):
    """One horizontal bar in a category-spend breakdown (a 'catalog' row: icon-color, label, bar, amount)."""

    fraction = NumericProperty(0.0)   # 0..1 of the max category in the list
    bar_color = ListProperty(theme.ACCENT)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, fraction=self._redraw)

    def _redraw(self, *_):
        self.canvas.after.clear()
        if self.width <= 0 or self.height <= 0:
            return
        track_h = min(10, self.height * 0.35)
        y = self.y + (self.height - track_h) / 2
        with self.canvas.after:
            Color(1, 1, 1, 0.10)
            RoundedRectangle(pos=(self.x, y), size=(self.width, track_h), radius=[track_h / 2])
            Color(*self.bar_color)
            fill_w = max(track_h, self.width * min(self.fraction, 1.0))
            RoundedRectangle(pos=(self.x, y), size=(fill_w, track_h), radius=[track_h / 2])


class DonutChart(Widget):
    """Category-share donut for the trends screen: one arc segment per category."""

    segments = ListProperty([])  # list of {"fraction": float, "color": (r,g,b,a)}
    ring_width = NumericProperty(16)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw, segments=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        if not self.segments or self.width <= 0 or self.height <= 0:
            return
        cx, cy = self.center_x, self.center_y
        r = min(self.width, self.height) / 2 - self.ring_width / 2 - 2
        start = 90.0  # start at 12 o'clock
        with self.canvas:
            Color(1, 1, 1, 0.08)
            Line(circle=(cx, cy, r), width=self.ring_width)
            for seg in self.segments:
                sweep = seg["fraction"] * 360.0
                Color(*seg["color"])
                Line(circle=(cx, cy, r, start, start + sweep), width=self.ring_width, cap="none")
                start += sweep
