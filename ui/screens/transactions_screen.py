"""
Transactions screen: responsive catalog list of all transactions with add/edit,
category auto-suggest, and duplicate-flag surfacing (stationery/household focus).
"""
from __future__ import annotations

from datetime import date

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField

from core.budget_engine import to_minor
from core.categorizer import learn_from_correction, suggest_category_id
from core.duplicate_detector import check_and_flag
from core.envelope_manager import record_expense
from db.database import get_db
from ui import theme
from ui.widgets.glass_card import GlassCard
from ui.widgets.transaction_item import TransactionRow


class TransactionsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "transactions"
        self.db = get_db()
        self.dialog = None
        self._category_menu = None
        self._selected_category_id = None
        self._build()

    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical")

        header = BoxLayout(orientation="horizontal", size_hint=(1, None), height=56,
                            padding=(theme.PADDING, 8))
        header.add_widget(MDLabel(text="Transactions", theme_text_color="Custom",
                                   text_color=theme.TEXT_PRIMARY, font_style="H6"))
        add_btn = MDRaisedButton(text="+ Add", md_bg_color=theme.ACCENT, pos_hint={"center_y": 0.5})
        add_btn.bind(on_release=lambda *_: self.open_add_dialog())
        header.add_widget(add_btn)
        root.add_widget(header)

        scroll = ScrollView()
        self.list_col = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=8,
                                   padding=(theme.PADDING, 4, theme.PADDING, 16))
        self.list_col.bind(minimum_height=self.list_col.setter("height"))
        scroll.add_widget(self.list_col)
        root.add_widget(scroll)
        self.add_widget(root)
        self.refresh_list()

    def refresh_list(self):
        self.list_col.clear_widgets()
        rows = self.db.query("SELECT * FROM transactions ORDER BY txn_date DESC, id DESC LIMIT 200")
        for row in rows:
            txn = dict(row)
            cat = self.db.query_one("SELECT * FROM categories WHERE id = ?", (txn["category_id"],)) \
                if txn["category_id"] else None
            self.list_col.add_widget(
                TransactionRow(txn, dict(cat) if cat else None, on_press=self._on_txn_press)
            )
        if not rows:
            self.list_col.add_widget(MDLabel(
                text="No transactions yet. Tap + Add to record your first one.",
                theme_text_color="Custom", text_color=theme.TEXT_MUTED, halign="center",
                size_hint=(1, None), height=60,
            ))

    def _on_txn_press(self, txn: dict):
        self.open_add_dialog(existing=txn)

    def open_add_dialog(self, existing: dict | None = None):
        self._selected_category_id = existing["category_id"] if existing else None
        content = BoxLayout(orientation="vertical", spacing=10, size_hint_y=None, height=280,
                             padding=(0, 8))

        self.merchant_field = MDTextField(hint_text="Merchant / description",
                                           text=(existing or {}).get("merchant", ""))
        self.amount_field = MDTextField(hint_text="Amount (₹)", input_filter="float",
                                         text=str((existing or {}).get("amount_minor", 0) / 100
                                                  if existing else ""))
        self.date_field = MDTextField(hint_text="Date (YYYY-MM-DD)",
                                       text=(existing or {}).get("txn_date", date.today().isoformat()))

        cats = self.db.query("SELECT id, name FROM categories ORDER BY name")
        cat_names = {c["id"]: c["name"] for c in cats}
        default_cat_name = cat_names.get(self._selected_category_id, "Select category")
        self.category_btn = MDFlatButton(text=default_cat_name, md_bg_color=theme.GLASS_FILL)

        menu_items = [
            {"text": c["name"], "viewclass": "OneLineListItem",
             "on_release": lambda cid=c["id"], name=c["name"]: self._pick_category(cid, name)}
            for c in cats
        ]
        self._category_menu = MDDropdownMenu(caller=self.category_btn, items=menu_items, width_mult=4)
        self.category_btn.bind(on_release=lambda *_: self._category_menu.open())

        content.add_widget(self.merchant_field)
        content.add_widget(self.amount_field)
        content.add_widget(self.date_field)
        content.add_widget(self.category_btn)

        self.dialog = MDDialog(
            title="Edit transaction" if existing else "Add transaction",
            type="custom", content_cls=content,
            buttons=[
                MDFlatButton(text="CANCEL", on_release=lambda *_: self.dialog.dismiss()),
                MDRaisedButton(text="SAVE", md_bg_color=theme.ACCENT,
                               on_release=lambda *_: self._save_txn(existing)),
            ],
        )
        self.dialog.open()

    def _pick_category(self, category_id: int, name: str):
        self._selected_category_id = category_id
        self.category_btn.text = name
        self._category_menu.dismiss()

    def _save_txn(self, existing: dict | None):
        merchant = self.merchant_field.text.strip()
        try:
            amount = float(self.amount_field.text or 0)
        except ValueError:
            amount = 0.0
        txn_date = self.date_field.text.strip() or date.today().isoformat()

        category_id = self._selected_category_id
        if category_id is None:
            category_id = suggest_category_id(self.db, merchant)

        if existing:
            self.db.update("transactions", existing["id"], {
                "merchant": merchant, "amount_minor": to_minor(amount),
                "txn_date": txn_date, "category_id": category_id,
            })
            txn_id = existing["id"]
        else:
            txn_id = record_expense(
                self.db, envelope_id=None, category_id=category_id, txn_date=txn_date,
                amount_major=amount, merchant=merchant, source="manual",
            )

        if category_id:
            learn_from_correction(self.db, merchant, category_id)
        match = check_and_flag(self.db, txn_id)

        self.dialog.dismiss()
        self.refresh_list()
        if match:
            self._notify_duplicate(match)

    def _notify_duplicate(self, match):
        note = MDDialog(
            title="Possible duplicate purchase",
            text=(f"This looks similar to a purchase already logged "
                  f"({match.reason}). Check Settings > Duplicates to review it."),
            buttons=[MDFlatButton(text="OK", on_release=lambda *_: note.dismiss())],
        )
        note.open()

    def on_pre_enter(self, *args):
        self.refresh_list()
