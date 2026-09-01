"""Single-row transaction card used in the Transactions catalog and Dashboard 'recent' list."""
from __future__ import annotations

from kivymd.uix.label import MDLabel
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.behaviors import RectangularRippleBehavior, TouchBehavior
from kivymd.icon_definitions import md_icons

from ui import theme
from ui.widgets.glass_card import GlassCard


def _safe_icon(name: str) -> str:
    return name if name in md_icons else "shape-outline"


class TransactionRow(RectangularRippleBehavior, TouchBehavior, GlassCard):
    """
    A tappable glass row: category color dot + icon, merchant/description, amount,
    and an optional duplicate-warning chip. Tap opens edit; long-press could offer delete.
    """

    def __init__(self, txn: dict, category: dict | None = None, on_press=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint=(1, None), height=64,
                          padding=(14, 8), spacing=12, **kwargs)
        self.txn = txn
        self.on_press_callback = on_press
        self.fill_color = theme.GLASS_FILL

        color = theme.category_color(category["color_hex"] if category else "#9E9E9E")
        icon_name = _safe_icon(category["icon"] if category else "shape-outline")

        from kivymd.uix.label import MDIcon
        icon_wrap = BoxLayout(size_hint=(None, 1), width=40)
        icon = MDIcon(icon=icon_name, theme_text_color="Custom", text_color=color, halign="center",
                       font_size="22sp")
        icon_wrap.add_widget(icon)
        self.add_widget(icon_wrap)

        text_col = BoxLayout(orientation="vertical", size_hint=(1, 1))
        title = txn.get("merchant") or txn.get("description") or "Transaction"
        title_lbl = MDLabel(text=title, theme_text_color="Custom", text_color=theme.TEXT_PRIMARY,
                             font_style="Subtitle1", halign="left", shorten=True, shorten_from="right")
        sub_bits = [txn.get("txn_date", "")]
        if category:
            sub_bits.append(category["name"])
        if txn.get("duplicate_of") and not txn.get("is_reviewed"):
            sub_bits.append("possible duplicate")
        sub_lbl = MDLabel(text="  •  ".join(b for b in sub_bits if b), theme_text_color="Custom",
                           text_color=theme.TEXT_SECONDARY, font_style="Caption", halign="left")
        text_col.add_widget(title_lbl)
        text_col.add_widget(sub_lbl)
        self.add_widget(text_col)

        amt = txn.get("amount_minor", 0) / 100
        sign = "-" if txn.get("txn_type") == "expense" else "+"
        amt_color = theme.DANGER if txn.get("txn_type") == "expense" else theme.SUCCESS
        amt_lbl = MDLabel(text=f"{sign}₹{amt:,.2f}", theme_text_color="Custom", text_color=amt_color,
                           font_style="Subtitle1", halign="right", size_hint=(None, 1), width=110)
        self.add_widget(amt_lbl)

    def on_release(self, *args):
        if self.on_press_callback:
            self.on_press_callback(self.txn)
