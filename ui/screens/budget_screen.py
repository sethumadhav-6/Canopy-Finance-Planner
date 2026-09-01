"""
Budget screen -- next month's projected budget per category, engine-suggested
from spend trends, editable by the user.
"""
from __future__ import annotations

from datetime import date

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField

from core import budget_engine
from core.analytics import shift_month
from db.database import get_db, to_major
from ui import theme
from ui.widgets.charts import CategoryBarRow
from ui.widgets.glass_card import GlassCard


class BudgetScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "budget"
        self.db = get_db()
        self._build()

    def _target_month(self) -> str:
        return shift_month(date.today().strftime("%Y-%m"), 1)

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical")

        target_month = self._target_month()
        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=56,
                            padding=(theme.PADDING, 8))
        header.add_widget(MDLabel(text=f"Budget for {target_month}", theme_text_color="Custom",
                                   text_color=theme.TEXT_PRIMARY, font_style="H6"))
        gen_btn = MDRaisedButton(text="Suggest from trend", md_bg_color=theme.ACCENT)
        gen_btn.bind(on_release=lambda *_: self._generate())
        header.add_widget(gen_btn)
        root.add_widget(header)

        scroll = ScrollView()
        self.col = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=8,
                              padding=(theme.PADDING, 4, theme.PADDING, 16))
        self.col.bind(minimum_height=self.col.setter("height"))
        scroll.add_widget(self.col)
        root.add_widget(scroll)
        self.add_widget(root)
        self.refresh()

    def _generate(self):
        target_month = self._target_month()
        suggestions = budget_engine.suggest_all_budgets(self.db, target_month)
        budget_engine.apply_budget_suggestions(self.db, suggestions, target_month)
        self.refresh()

    def refresh(self):
        self.col.clear_widgets()
        target_month = self._target_month()
        rows = budget_engine.budget_vs_actual(self.db, target_month)
        # For next month, 'actual' is naturally 0 -- show planned amount + basis instead,
        # and let this same table double as a "how did last month go" view when viewing
        # the current month via the same engine call.
        if not rows:
            self.col.add_widget(MDLabel(
                text="No budget set yet. Tap 'Suggest from trend' to auto-generate one "
                     "from your recent spending.",
                theme_text_color="Custom", text_color=theme.TEXT_MUTED, halign="center",
                size_hint=(1, None), height=80,
            ))
            return
        max_planned = max(r["planned_minor"] for r in rows) or 1
        for r in rows:
            card = GlassCard(orientation="vertical", size_hint=(1, None), height=76, padding=(14, 8))
            top = BoxLayout(orientation="horizontal", size_hint=(1, None), height=22)
            top.add_widget(MDLabel(text=r["name"], theme_text_color="Custom",
                                    text_color=theme.TEXT_PRIMARY))
            basis_txt = "auto" if r["basis"] == "auto" else "manual"
            top.add_widget(MDLabel(text=f"₹{to_major(r['planned_minor']):,.0f}/mo ({basis_txt})",
                                    theme_text_color="Custom", text_color=theme.TEXT_SECONDARY,
                                    halign="right"))
            card.add_widget(top)
            bar = CategoryBarRow(size_hint=(1, None), height=12,
                                  fraction=r["planned_minor"] / max_planned,
                                  bar_color=theme.category_color(r["color_hex"]))
            card.add_widget(bar)
            edit_btn = MDFlatButton(text="Edit", size_hint=(None, None), size=(60, 24),
                                     pos_hint={"right": 1})
            edit_btn.bind(on_release=lambda *_, cid=r["category_id"], cur=r["planned_minor"]:
                          self._open_edit(cid, cur))
            card.add_widget(edit_btn)
            self.col.add_widget(card)

    def _open_edit(self, category_id: int, current_minor: int):
        field = MDTextField(hint_text="Planned amount (₹)", input_filter="float",
                             text=str(to_major(current_minor)))
        dialog = MDDialog(
            title="Edit budget", type="custom", content_cls=field,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda *_: dialog.dismiss()),
                MDRaisedButton(text="SAVE", md_bg_color=theme.ACCENT,
                               on_release=lambda *_: self._save_edit(dialog, field, category_id)),
            ],
        )
        dialog.open()

    def _save_edit(self, dialog, field, category_id: int):
        try:
            amount = float(field.text or 0)
        except ValueError:
            amount = 0.0
        budget_engine.set_manual_budget(self.db, self._target_month(), category_id, amount)
        dialog.dismiss()
        self.refresh()

    def on_pre_enter(self, *args):
        self.refresh()
