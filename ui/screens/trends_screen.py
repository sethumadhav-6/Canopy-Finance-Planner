"""
Trends screen: 6-month spend trend line + this month's category breakdown
(donut + ranked bar catalog) -- the "where am I overspending" visual view.
"""
from __future__ import annotations

from datetime import date

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

from core import analytics
from db.database import get_db, to_major
from ui import theme
from ui.widgets.charts import CategoryBarRow, DonutChart, TrendLineChart
from ui.widgets.glass_card import GlassCard


class TrendsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "trends"
        self.db = get_db()
        self._build()

    def _build(self):
        self.clear_widgets()
        scroll = ScrollView()
        col = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=theme.SPACING,
                         padding=theme.PADDING)
        col.bind(minimum_height=col.setter("height"))

        month = date.today().strftime("%Y-%m")

        col.add_widget(MDLabel(text="Trends", theme_text_color="Custom",
                                text_color=theme.TEXT_PRIMARY, font_style="H6",
                                size_hint=(1, None), height=32))

        # -- 6-month trend line -----------------------------------------------
        trend_card = GlassCard(orientation="vertical", size_hint=(1, None), height=220)
        trend_card.add_widget(MDLabel(text="Last 6 months", theme_text_color="Custom",
                                       text_color=theme.TEXT_SECONDARY, font_style="Caption",
                                       size_hint=(1, None), height=20))
        trend_data = analytics.monthly_trend(self.db, month, n_months=6)
        chart = TrendLineChart(
            points_data=[{"label": d["month"][5:], "value": d["total_major"]} for d in trend_data],
            size_hint=(1, 1),
        )
        trend_card.add_widget(chart)
        col.add_widget(trend_card)

        # -- category breakdown: donut + ranked list ---------------------------
        breakdown = analytics.spend_by_category(self.db, month)
        if breakdown:
            total = sum(b["total_minor"] for b in breakdown) or 1
            donut_card = GlassCard(orientation="horizontal", size_hint=(1, None), height=200,
                                    spacing=16)
            donut = DonutChart(
                segments=[{"fraction": b["total_minor"] / total,
                           "color": theme.category_color(b["color_hex"])} for b in breakdown],
                size_hint=(None, 1), width=170,
            )
            donut_card.add_widget(donut)

            legend = BoxLayout(orientation="vertical", size_hint=(1, 1), spacing=2)
            for b in breakdown[:6]:
                row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=22)
                row.add_widget(MDLabel(text=b["name"], theme_text_color="Custom",
                                        text_color=theme.TEXT_PRIMARY, font_style="Caption"))
                pct = b["total_minor"] / total * 100
                row.add_widget(MDLabel(text=f"{pct:.0f}%", theme_text_color="Custom",
                                        text_color=theme.TEXT_SECONDARY, font_style="Caption",
                                        halign="right", size_hint=(None, 1), width=50))
                legend.add_widget(row)
            donut_card.add_widget(legend)
            col.add_widget(donut_card)

            col.add_widget(MDLabel(text="By category", theme_text_color="Custom",
                                    text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                    size_hint=(1, None), height=28))
            max_total = max(b["total_minor"] for b in breakdown)
            for b in breakdown:
                row_card = GlassCard(orientation="horizontal", size_hint=(1, None), height=48,
                                      padding=(14, 6), spacing=10)
                row_card.add_widget(MDLabel(text=b["name"], theme_text_color="Custom",
                                             text_color=theme.TEXT_PRIMARY, size_hint=(0.35, 1)))
                bar = CategoryBarRow(size_hint=(0.45, 1), fraction=b["total_minor"] / max_total,
                                      bar_color=theme.category_color(b["color_hex"]))
                row_card.add_widget(bar)
                row_card.add_widget(MDLabel(text=f"₹{to_major(b['total_minor']):,.0f}",
                                             theme_text_color="Custom", text_color=theme.TEXT_SECONDARY,
                                             halign="right", size_hint=(0.2, 1)))
                col.add_widget(row_card)
        else:
            col.add_widget(MDLabel(text="No spending recorded yet this month.",
                                    theme_text_color="Custom", text_color=theme.TEXT_MUTED,
                                    halign="center", size_hint=(1, None), height=60))

        scroll.add_widget(col)
        self.add_widget(scroll)

    def on_pre_enter(self, *args):
        self._build()
