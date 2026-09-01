"""
Canopy Finance Planner -- offline personal finance app.
Entry point: sets up the KivyMD app shell (glass background + bottom nav across
Dashboard / Transactions / Envelopes / Trends / Budget / Settings) and initializes
the local SQLite database on first launch.
"""
from __future__ import annotations

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.floatlayout import MDFloatLayout

from db.database import get_db
from ui import theme
from ui.screens.budget_screen import BudgetScreen
from ui.screens.dashboard_screen import DashboardScreen
from ui.screens.envelopes_screen import EnvelopesScreen
from ui.screens.settings_screen import SettingsScreen
from ui.screens.transactions_screen import TransactionsScreen
from ui.screens.trends_screen import TrendsScreen
from ui.widgets.glass_card import GradientBackground

# Desktop dev window sized like a typical phone in portrait, so the responsive
# layout can be sanity-checked without a device/emulator. Ignored on Android.
Window.size = (390, 780)


class CanopyFinanceApp(MDApp):
    def build(self):
        self.title = "Canopy Finance Planner"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"

        # Initialize (and, on first run, seed) the offline database before any
        # screen queries it.
        get_db()

        root = MDFloatLayout()
        root.add_widget(GradientBackground(size_hint=(1, 1)))

        # NOTE: color kwargs are set *after* construction, not passed into __init__ --
        # KivyMD 1.2.0's MDBottomNavigation reacts to those properties via an on_-callback
        # that touches self.ids.tab_bar, which doesn't exist yet while __init__ is still
        # applying constructor kwargs. Setting them post-construction avoids that crash.
        nav = MDBottomNavigation()
        nav.panel_color = (0.09, 0.10, 0.19, 0.92)
        nav.selected_color_background = theme.ACCENT
        nav.text_color_active = theme.TEXT_PRIMARY
        nav.text_color_normal = theme.TEXT_MUTED

        tabs = [
            ("dashboard", "Home", "view-dashboard-outline", DashboardScreen),
            ("transactions", "Transactions", "format-list-bulleted", TransactionsScreen),
            ("envelopes", "Envelopes", "wallet-outline", EnvelopesScreen),
            ("trends", "Trends", "chart-line", TrendsScreen),
            ("budget", "Budget", "calculator-variant-outline", BudgetScreen),
            ("settings", "Settings", "cog-outline", SettingsScreen),
        ]
        for name, text, icon, screen_cls in tabs:
            item = MDBottomNavigationItem(name=name, text=text, icon=icon)
            item.add_widget(screen_cls())
            nav.add_widget(item)

        root.add_widget(nav)
        return root


def main():
    CanopyFinanceApp().run()


if __name__ == "__main__":
    main()
