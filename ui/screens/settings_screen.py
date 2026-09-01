"""
Settings screen: review flagged duplicate purchases, manage categories, and
Phase 2's SMS auto-import -- a review queue where every parsed SMS sits until
the user approves or rejects it, plus a scan trigger that only does anything
on a real Android device.
"""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.selectioncontrol import MDSwitch

from core.duplicate_detector import resolve_duplicate, unresolved_duplicates
from core.sms_import import approve_sms, pending_sms_staging, reject_sms
from db.database import get_db, to_major
from ui import theme
from ui.widgets.glass_card import GlassCard


class SettingsScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "settings"
        self.db = get_db()
        self.sms_enabled = False
        self._build()

    def _build(self):
        self.clear_widgets()
        scroll = ScrollView()
        col = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=theme.SPACING,
                         padding=theme.PADDING)
        col.bind(minimum_height=col.setter("height"))

        col.add_widget(MDLabel(text="Settings", theme_text_color="Custom",
                                text_color=theme.TEXT_PRIMARY, font_style="H6",
                                size_hint=(1, None), height=32))

        # -- duplicate review -----------------------------------------------------
        col.add_widget(MDLabel(text="Possible duplicate purchases", theme_text_color="Custom",
                                text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                size_hint=(1, None), height=28))
        self.dup_col = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=8)
        self.dup_col.bind(minimum_height=self.dup_col.setter("height"))
        col.add_widget(self.dup_col)
        self._refresh_duplicates()

        # -- data & privacy --------------------------------------------------------
        col.add_widget(MDLabel(text="Data & privacy", theme_text_color="Custom",
                                text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                size_hint=(1, None), height=28))
        privacy_card = GlassCard(orientation="vertical", size_hint=(1, None), height=90, padding=14)
        privacy_card.add_widget(MDLabel(
            text="All data stays in a local SQLite database on this device. Nothing is "
                 "uploaded anywhere. SMS parsing below also runs entirely on-device.",
            theme_text_color="Custom", text_color=theme.TEXT_SECONDARY, font_style="Caption",
        ))
        col.add_widget(privacy_card)

        # -- SMS auto-import (Phase 2) ------------------------------------------------
        col.add_widget(MDLabel(text="SMS auto-import", theme_text_color="Custom",
                                text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                size_hint=(1, None), height=28))
        sms_card = GlassCard(orientation="vertical", size_hint=(1, None), height=180, padding=14, spacing=6)
        row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=32)
        row.add_widget(MDLabel(text="Scan SMS for bank/UPI transactions", theme_text_color="Custom",
                                text_color=theme.TEXT_PRIMARY))
        self.sms_switch = MDSwitch(active=self.sms_enabled)
        self.sms_switch.bind(active=self._on_sms_toggle)
        row.add_widget(self.sms_switch)
        sms_card.add_widget(row)
        sms_card.add_widget(MDLabel(
            text="Reads SMS on-device only (READ_SMS permission) -- nothing is ever sent off "
                 "the phone. Every parsed message lands below for you to approve or reject; "
                 "nothing is added to your transactions automatically. This only works on a "
                 "real Android device/build, not in this desktop preview. Google Play treats "
                 "READ_SMS as a sensitive permission for finance apps -- see the README before "
                 "submitting a store build.",
            theme_text_color="Custom", text_color=theme.TEXT_MUTED, font_style="Caption",
        ))
        self.scan_btn = MDRaisedButton(text="Scan inbox now", md_bg_color=theme.ACCENT,
                                        disabled=not self.sms_enabled)
        self.scan_btn.bind(on_release=lambda *_: self._scan_inbox())
        sms_card.add_widget(self.scan_btn)
        col.add_widget(sms_card)

        col.add_widget(MDLabel(text="Pending SMS transactions", theme_text_color="Custom",
                                text_color=theme.TEXT_PRIMARY, font_style="Subtitle1",
                                size_hint=(1, None), height=28))
        self.sms_col = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=8)
        self.sms_col.bind(minimum_height=self.sms_col.setter("height"))
        col.add_widget(self.sms_col)
        self._refresh_sms_queue()

        scroll.add_widget(col)
        self.add_widget(scroll)

    def _on_sms_toggle(self, switch, value):
        self.sms_enabled = value
        self.scan_btn.disabled = not value

    def _scan_inbox(self):
        try:
            # Deliberately NOT named "android.*" -- python-for-android injects its own
            # top-level "android" package at runtime, and a local module of the same
            # name would risk shadowing/colliding with it. Lives under integrations/
            # instead; still only importable inside an actual Android build.
            from integrations.android_sms import request_permission_and_scan
        except Exception:
            note = MDDialog(
                title="Not available on this build",
                text="SMS scanning only works in a real Android build/device -- not in this "
                     "desktop preview. Nothing to scan here.",
                buttons=[MDFlatButton(text="OK", on_release=lambda *_: note.dismiss())],
            )
            note.open()
            return
        result = request_permission_and_scan(self.db)
        self._refresh_sms_queue()
        note = MDDialog(
            title="Inbox scan complete",
            text=f"Scanned {result.scanned} messages, found {result.staged} possible "
                 f"transaction(s) waiting for your review below.",
            buttons=[MDFlatButton(text="OK", on_release=lambda *_: note.dismiss())],
        )
        note.open()

    def _refresh_sms_queue(self):
        self.sms_col.clear_widgets()
        pending = pending_sms_staging(self.db)
        if not pending:
            self.sms_col.add_widget(MDLabel(
                text="Nothing pending. Approved/rejected messages won't show here again.",
                theme_text_color="Custom", text_color=theme.TEXT_MUTED, font_style="Caption",
                size_hint=(1, None), height=28,
            ))
            return
        for s in pending:
            card = GlassCard(orientation="vertical", size_hint=(1, None), height=112,
                              padding=12, spacing=4)
            top = BoxLayout(orientation="horizontal", size_hint=(1, None), height=22)
            sign = "-" if s["parsed_txn_type"] == "expense" else "+"
            top.add_widget(MDLabel(
                text=f"{s['parsed_merchant'] or 'Unknown'}  {sign}₹{to_major(s['parsed_amount_minor']):,.2f}",
                theme_text_color="Custom", text_color=theme.TEXT_PRIMARY, font_style="Body1"))
            conf_pct = int((s["confidence"] or 0) * 100)
            conf_color = theme.SUCCESS if conf_pct >= 70 else theme.WARNING
            top.add_widget(MDLabel(text=f"{conf_pct}% match", theme_text_color="Custom",
                                    text_color=conf_color, halign="right", font_style="Caption"))
            card.add_widget(top)
            card.add_widget(MDLabel(
                text=f"{s['parsed_txn_date']}  ·  {s['sender'] or 'Unknown sender'}",
                theme_text_color="Custom", text_color=theme.TEXT_SECONDARY, font_style="Caption",
            ))
            btn_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=32, spacing=8)
            approve_btn = MDFlatButton(text="Approve", text_color=theme.SUCCESS,
                                        on_release=lambda *_, sid=s["id"]: self._approve(sid))
            reject_btn = MDFlatButton(text="Reject", text_color=theme.DANGER,
                                       on_release=lambda *_, sid=s["id"]: self._reject(sid))
            btn_row.add_widget(approve_btn)
            btn_row.add_widget(reject_btn)
            card.add_widget(btn_row)
            self.sms_col.add_widget(card)

    def _approve(self, staging_id: int):
        approve_sms(self.db, staging_id)
        self._refresh_sms_queue()

    def _reject(self, staging_id: int):
        reject_sms(self.db, staging_id)
        self._refresh_sms_queue()

    def _refresh_duplicates(self):
        self.dup_col.clear_widgets()
        dups = unresolved_duplicates(self.db)
        if not dups:
            self.dup_col.add_widget(MDLabel(
                text="No unresolved duplicate flags.", theme_text_color="Custom",
                text_color=theme.TEXT_MUTED, font_style="Caption",
                size_hint=(1, None), height=28,
            ))
            return
        for d in dups:
            card = GlassCard(orientation="vertical", size_hint=(1, None), height=92, padding=12, spacing=4)
            card.add_widget(MDLabel(
                text=f"{d.get('merchant') or 'Purchase'} — ₹{to_major(d['amount_minor']):,.2f} "
                     f"on {d['txn_date']}",
                theme_text_color="Custom", text_color=theme.TEXT_PRIMARY, font_style="Body2",
            ))
            card.add_widget(MDLabel(
                text=f"Looks similar to ₹{to_major(d['matched_amount_minor']):,.2f} on "
                     f"{d['matched_date']} (score {d['duplicate_score']:.2f})",
                theme_text_color="Custom", text_color=theme.TEXT_SECONDARY, font_style="Caption",
            ))
            btn_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=32, spacing=8)
            keep_btn = MDFlatButton(text="Keep both", on_release=lambda *_, tid=d["id"]: self._resolve(tid, True))
            del_btn = MDFlatButton(text="It's a duplicate, remove", text_color=theme.DANGER,
                                    on_release=lambda *_, tid=d["id"]: self._resolve(tid, False))
            btn_row.add_widget(keep_btn)
            btn_row.add_widget(del_btn)
            card.add_widget(btn_row)
            self.dup_col.add_widget(card)

    def _resolve(self, txn_id: int, keep: bool):
        resolve_duplicate(self.db, txn_id, keep)
        self._refresh_duplicates()

    def on_pre_enter(self, *args):
        self._refresh_duplicates()
        self._refresh_sms_queue()
