"""
Dashboard -- the home screen: this month's total spend, budget health, quick
overspend alerts, recurring-vault drift, and a short "recent transactions" list.
"""
from __future__ import annotations

from datetime import date

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen

from core import analytics
from core.envelope_manager import all_envelope_statuses
from db.database import get_db, to_major
from ui import theme
from ui.widgets.envelope_card import EnvelopeCard
from ui.widgets.glass_card import GlassCard, GradientCard
from ui.widgets.transaction_item import TransactionRow


class DashboardScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "dashboard"
        self.db = get_db()
        self._build()

    def _build(self):
        self.clear_widgets()
        scroll = ScrollView()
        col = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=theme.SPACING,
                         padding=theme.PADDING)
        col.bind(minimum_height=col.setter("height"))

        month = date.today().strftime("%Y-%m")

        # -- headline spend card -------------------------------------------------
        total_minor = analytics.monthly_total(self.db, month, "expense")
        headline = GradientCard(orientation="vertical", size_hint=(1, None), height=118)
        headline.add_widget(MDLabel(text=f"This month's spend  ·  {month}", theme_text_color="Custom",
                                     text_color=theme.TEXT_ON_GOLD_SOFT, font_style="Caption"))
        headline.add_widget(MDLabel(text=f"₹{to_major(total_minor):,.2f}", theme_text_color="Custom",
                                     text_color=theme.TEXT_ON_GOLD, font_style="H4", bold=True))
        col.add_widget(headline)

        # -- overspend alerts -----------------------------------------------------
        alerts = analytics.top_overspend_alerts(self.db, month, threshold_pct=90.0)
        if alerts:
            col.add_widget(MDLabel(text="Where you're spending too much", theme_text_color="Custom",
                                    text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                    size_hint=(1, None), height=28))
            for a in alerts[:5]:
                card = GlassCard(orientation="horizontal", size_hint=(1, None), height=52,
                                  padding=(14, 8))
                card.add_widget(MDLabel(text=a["name"], theme_text_color="Custom",
                                         text_color=theme.TEXT_PRIMARY))
                pct_color = theme.DANGER if a["pct"] >= 100 else theme.WARNING
                card.add_widget(MDLabel(
                    text=f"{a['pct']:.0f}% of ₹{to_major(a['planned_minor']):,.0f} budget",
                    theme_text_color="Custom", text_color=pct_color, halign="right"))
                col.add_widget(card)

        # -- recurring vault drift -------------------------------------------------
        drift = [d for d in analytics.recurring_vault_drift(self.db, month) if abs(d["drift_pct"]) >= 10]
        if drift:
            col.add_widget(MDLabel(text="Recurring vault cost changes", theme_text_color="Custom",
                                    text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                    size_hint=(1, None), height=28))
            for d in drift[:4]:
                card = GlassCard(orientation="horizontal", size_hint=(1, None), height=52, padding=(14, 8))
                card.add_widget(MDLabel(text=d["name"], theme_text_color="Custom",
                                         text_color=theme.TEXT_PRIMARY))
                trend_color = theme.DANGER if d["drift_pct"] > 0 else theme.SUCCESS
                arrow = "▲" if d["drift_pct"] > 0 else "▼"
                card.add_widget(MDLabel(text=f"{arrow} {abs(d['drift_pct']):.0f}% vs usual",
                                         theme_text_color="Custom", text_color=trend_color, halign="right"))
                col.add_widget(card)

        # -- envelopes summary (top 3) ----------------------------------------------
        statuses = all_envelope_statuses(self.db, month)
        if statuses:
            col.add_widget(MDLabel(text="Envelopes", theme_text_color="Custom",
                                    text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                    size_hint=(1, None), height=28))
            for s in statuses[:3]:
                col.add_widget(EnvelopeCard(s))

        # -- recent transactions -----------------------------------------------------
        recent = self.db.query(
            "SELECT * FROM transactions ORDER BY txn_date DESC, id DESC LIMIT 8"
        )
        if recent:
            col.add_widget(MDLabel(text="Recent activity", theme_text_color="Custom",
                                    text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                    size_hint=(1, None), height=28))
            for row in recent:
                txn = dict(row)
                cat = self.db.query_one("SELECT * FROM categories WHERE id = ?", (txn["category_id"],)) \
                    if txn["category_id"] else None
                col.add_widget(TransactionRow(txn, dict(cat) if cat else None))

        scroll.add_widget(col)
        self.add_widget(scroll)

    def on_pre_enter(self, *args):
        self._build()
