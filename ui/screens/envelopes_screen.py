"""
Envelopes screen -- the custom offline envelope catalog: discretionary buckets,
savings goals, and recurring vaults (subscriptions/rent/EMIs) side by side with
allocated vs spent, in a responsive grid (1 column on narrow phones, 2 on wide
screens/tablets).
"""
from __future__ import annotations

from datetime import date

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField

from core.envelope_manager import all_envelope_statuses, create_envelope
from db.database import get_db
from ui import theme
from ui.widgets.envelope_card import EnvelopeCard

WIDE_BREAKPOINT_DP = 560


class EnvelopesScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "envelopes"
        self.db = get_db()
        self._selected_type = "discretionary"
        self._type_menu = None
        self._build()

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical")

        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=56,
                            padding=(theme.PADDING, 8))
        header.add_widget(MDLabel(text="Envelopes", theme_text_color="Custom",
                                   text_color=theme.TEXT_PRIMARY, font_style="H6"))
        add_btn = MDRaisedButton(text="+ New envelope", md_bg_color=theme.ACCENT)
        add_btn.bind(on_release=lambda *_: self.open_add_dialog())
        header.add_widget(add_btn)
        root.add_widget(header)

        scroll = ScrollView()
        self.grid = GridLayout(cols=1, size_hint=(1, None), spacing=theme.SPACING,
                                padding=(theme.PADDING, 4, theme.PADDING, 16))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)
        self.add_widget(root)
        self.bind(size=self._update_columns)
        self.refresh()

    def _update_columns(self, *_):
        self.grid.cols = 2 if self.width >= WIDE_BREAKPOINT_DP else 1

    def refresh(self):
        self.grid.clear_widgets()
        month = date.today().strftime("%Y-%m")
        statuses = all_envelope_statuses(self.db, month)
        if not statuses:
            self.grid.add_widget(MDLabel(
                text="No envelopes yet. Create one for rent, subscriptions, groceries...",
                theme_text_color="Custom", text_color=theme.TEXT_MUTED, halign="center",
                size_hint=(1, None), height=60,
            ))
            return
        for s in statuses:
            card = EnvelopeCard(s)
            card.size_hint = (1, None)
            self.grid.add_widget(card)

    def open_add_dialog(self):
        content = BoxLayout(orientation="vertical", spacing=10, size_hint_y=None, height=260,
                             padding=(0, 8))
        self.name_field = MDTextField(hint_text="Envelope name (e.g. Netflix, Rent, Groceries)")
        self.amount_field = MDTextField(hint_text="Monthly allocation (₹)", input_filter="float")

        type_btn = MDFlatButton(text="Discretionary", md_bg_color=theme.GLASS_FILL)
        type_items = [
            {"text": t, "viewclass": "OneLineListItem",
             "on_release": lambda tv=t: self._pick_type(tv, type_btn)}
            for t in ["Discretionary", "Recurring vault", "Savings goal"]
        ]
        self._type_menu = MDDropdownMenu(caller=type_btn, items=type_items, width_mult=4)
        type_btn.bind(on_release=lambda *_: self._type_menu.open())

        content.add_widget(self.name_field)
        content.add_widget(self.amount_field)
        content.add_widget(type_btn)

        self.dialog = MDDialog(
            title="New envelope", type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda *_: self.dialog.dismiss()),
                MDRaisedButton(text="CREATE", md_bg_color=theme.ACCENT,
                               on_release=lambda *_: self._create()),
            ],
        )
        self.dialog.open()

    def _pick_type(self, label: str, btn):
        mapping = {"Discretionary": "discretionary", "Recurring vault": "recurring_vault",
                   "Savings goal": "savings_goal"}
        self._selected_type = mapping[label]
        btn.text = label
        self._type_menu.dismiss()

    def _create(self):
        name = self.name_field.text.strip()
        try:
            amount = float(self.amount_field.text or 0)
        except ValueError:
            amount = 0.0
        if name:
            create_envelope(self.db, name=name, envelope_type=self._selected_type,
                             monthly_allocation_major=amount, rollover_enabled=True)
        self.dialog.dismiss()
        self.refresh()

    def on_pre_enter(self, *args):
        self.refresh()
