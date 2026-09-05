import sqlite3
from telethon.sessions.sqlite import SQLiteSession

_patched = False

def apply_telethon_sqlite_patch():
    """
    Configura a sessão SQLite interna do Telethon com timeout de 30 segundos
    e modo WAL para prevenir o erro 'database is locked'.
    """
    global _patched
    if _patched:
        return

    def _safe_cursor(self):
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.filename,
                check_same_thread=False,
                timeout=30.0
            )
            try:
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
            except Exception:
                pass
        return self._conn.cursor()

    SQLiteSession._cursor = _safe_cursor
    _patched = True
