"""Envelope 'catalog' card: allocated vs spent, progress bar, rollover + recurring-vault badges."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.label import MDLabel

from core.models import EnvelopeStatus
from db.database import to_major
from ui import theme
from ui.widgets.charts import CategoryBarRow
from ui.widgets.glass_card import GlassCard


class EnvelopeCard(GlassCard):
    def __init__(self, status: EnvelopeStatus, on_press=None, **kwargs):
        super().__init__(orientation="vertical", size_hint=(1, None), height=118,
                          padding=(16, 12), spacing=6, **kwargs)
        self.status = status
        self.fill_color = theme.GLASS_FILL_ELEVATED if status.is_over else theme.GLASS_FILL

        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=24)
        name_lbl = MDLabel(text=status.envelope.name, theme_text_color="Custom",
                            text_color=theme.TEXT_PRIMARY, font_style="Subtitle1")
        header.add_widget(name_lbl)
        if status.envelope.envelope_type == "recurring_vault":
            badge = MDLabel(text="VAULT", theme_text_color="Custom", text_color=theme.TEXT_MUTED,
                             font_style="Caption", size_hint=(None, 1), width=60, halign="right")
            header.add_widget(badge)
        self.add_widget(header)

        bar = CategoryBarRow(size_hint=(1, None), height=14,
                              fraction=status.pct_used / 100.0,
                              bar_color=theme.status_color(status.pct_used))
        self.add_widget(bar)

        footer = BoxLayout(orientation="horizontal", size_hint=(1, None), height=20)
        spent_lbl = MDLabel(
            text=f"₹{to_major(status.spent_minor):,.0f} of ₹{to_major(status.allocated_minor + status.rollover_in_minor):,.0f}",
            theme_text_color="Custom", text_color=theme.TEXT_SECONDARY, font_style="Caption",
        )
        remaining = to_major(status.remaining_minor)
        remain_color = theme.DANGER if status.is_over else theme.TEXT_SECONDARY
        remain_text = f"₹{abs(remaining):,.0f} over" if status.is_over else f"₹{remaining:,.0f} left"
        remain_lbl = MDLabel(text=remain_text, theme_text_color="Custom", text_color=remain_color,
                              font_style="Caption", halign="right")
        footer.add_widget(spent_lbl)
        footer.add_widget(remain_lbl)
        self.add_widget(footer)
