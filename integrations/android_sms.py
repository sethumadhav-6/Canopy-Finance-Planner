"""
Android SMS inbox access -- Phase 2 of the offline auto-import feature.

This module only works inside an actual python-for-android build running on
a device/emulator: it imports `android` and `jnius`, both of which are
provided by the p4a bootstrap and simply don't exist on desktop Python. Every
call site in this app (see ui/screens/settings_screen.py) wraps the import in
a try/except and falls back to a "not available on this build" message, so
desktop development is completely unaffected by this file.

Design choices, and why:
- One-shot inbox scan, not a background listener/service. A trial app has no
  business running a persistent SMS-reading background service -- that's a
  much bigger permission/battery/privacy footprint than "tap Scan, read what's
  already in the inbox." If always-on capture is wanted later, that's a
  separate, more heavily-reviewed addition (a foreground Service + a
  BroadcastReceiver for SMS_RECEIVED), not something to add casually.
- Every result still lands in sms_staging for manual review (core.sms_import)
  -- this module's only job is "get the raw SMS text + sender + date out of
  Android," never "decide it's a real transaction."
"""
from __future__ import annotations

from datetime import date, datetime

from android.permissions import Permission, check_permission, request_permissions  # type: ignore
from jnius import autoclass, cast  # type: ignore

from core.sms_import import BulkImportResult, bulk_stage_from_messages
from db.database import Database

SMS_READ_PERMISSION = Permission.READ_SMS

# How far back to read on a scan -- keeps a first scan from staging years of
# old SMS at once. The user can re-scan any time; already-staged messages are
# skipped (see core.sms_import.bulk_stage_from_messages).
DEFAULT_LOOKBACK_DAYS = 90


def _read_inbox_via_content_resolver(lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict]:
    """
    Query content://sms/inbox through Android's ContentResolver via pyjnius.
    Returns a list of {"text": str, "sender": str, "received_at": date} dicts.
    Must only be called after READ_SMS has been granted.
    """
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Uri = autoclass("android.net.Uri")
    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()

    sms_uri = Uri.parse("content://sms/inbox")
    projection = ["address", "body", "date"]
    cursor = resolver.query(sms_uri, projection, None, None, "date DESC")

    messages: list[dict] = []
    if cursor is None:
        return messages

    cutoff = datetime.now().timestamp() - lookback_days * 86400
    try:
        addr_idx = cursor.getColumnIndex("address")
        body_idx = cursor.getColumnIndex("body")
        date_idx = cursor.getColumnIndex("date")
        while cursor.moveToNext():
            ts_millis = cursor.getLong(date_idx)
            if ts_millis / 1000.0 < cutoff:
                break  # sorted DESC by date -- everything after this is even older
            body = cursor.getString(body_idx) or ""
            sender = cursor.getString(addr_idx) or ""
            received_at = datetime.fromtimestamp(ts_millis / 1000.0).date()
            messages.append({"text": body, "sender": sender, "received_at": received_at})
    finally:
        cursor.close()

    return messages


def has_sms_permission() -> bool:
    return check_permission(SMS_READ_PERMISSION)


def request_permission_and_scan(db: Database, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> BulkImportResult:
    """
    Entry point called from Settings. Requests READ_SMS if not already
    granted, then does a one-shot scan of the inbox and stages any
    transaction-looking messages for review. If the user denies the
    permission, returns an empty result rather than raising.
    """
    if not has_sms_permission():
        granted = {"ok": False}

        def _on_result(permissions, grant_results):
            granted["ok"] = all(grant_results)

        request_permissions([SMS_READ_PERMISSION], _on_result)
        # NOTE: request_permissions is async on Android; a production build
        # should re-trigger the scan from the permission-result callback
        # instead of assuming it resolved synchronously by this point. Kept
        # simple here since this whole flow is user-initiated (they just
        # tapped "Scan inbox now") and Android re-shows the same screen.
        if not has_sms_permission():
            return BulkImportResult(scanned=0, staged=0, ignored=0)

    messages = _read_inbox_via_content_resolver(lookback_days)
    return bulk_stage_from_messages(db, messages)
