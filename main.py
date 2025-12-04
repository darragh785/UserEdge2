"""
NiceGUI Admin app for managing Users (PostgreSQL) and Logging in on Raspberry Pi.

Requirements (install):
    pip install nicegui psycopg[binary] bcrypt python-dotenv

Notes:
    - Uses psycopg3.
    - Sets users.updated_at on create/update.
    - Passwords are stored as bcrypt hashes. When editing a user, leave "New Password"
      blank to keep the existing hash.
    - Roles: enter comma-separated values; saved as text[] in PostgreSQL.

main.py (final):
    - When APP_PROFILE=admin (default): runs the Users + Edges Admin SPA at "/".
    - When APP_PROFILE=pi: "/" redirects to "/rpi-login", which shows the RPi login page.
"""

from nicegui import ui, app
from dotenv import load_dotenv
from db_connector_pg import PostgresConnector
from user_admin_spa import register_admin_spa
import os

load_dotenv()

# --- read .env (with sensible fallbacks) ---
profile = os.getenv('APP_PROFILE', 'admin').lower()
host = os.getenv('HOST', '0.0.0.0')
port = int(os.getenv('PORT', '8080'))
title = os.getenv('APP_TITLE', 'Users Admin')
favicon = os.getenv('APP_FAVICON', '')  # empty by default, as in notes
secret = os.getenv('STORAGE_SECRET', 'abcdefhijklmnop')
dark = os.getenv('APP_DARK', 'False')

repo = PostgresConnector()


@ui.page('/rpi-login')
def rpi_login():
    """Raspberry Pi login UI (edge login)."""
    # lazy import to avoid circular imports
    from rpi_login_page import RpiLoginPage
    RpiLoginPage(repo)


# --- Route behaviour depends on APP_PROFILE ---
if profile == 'pi':

    @ui.page('/')
    def root_redirect():
        """On Pi profile, redirect root to /rpi-login."""
        ui.timer(0.01, lambda: ui.navigate.to('/rpi-login'), once=True)

else:
    # On admin profile, register the full Users + Edges Admin SPA at "/"
    register_admin_spa(repo)


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        host=host,
        port=port,
        title=title,
        favicon=favicon,
        dark=dark,
        storage_secret=secret,
        reload=False,
    )
