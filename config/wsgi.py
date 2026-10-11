"""
WSGI config for Real Estate Construction Management System.
"""
import os
import shutil
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# In Vercel serverless environment, ensure SQLite database is copied to writable /tmp
if os.environ.get('VERCEL'):
    try:
        base_dir = Path(__file__).resolve().parent.parent
        bundled_db = base_dir / 'db.sqlite3'
        tmp_db = Path('/tmp/db.sqlite3')
        if not tmp_db.exists() or tmp_db.stat().st_size == 0:
            if bundled_db.exists() and bundled_db.stat().st_size > 0:
                tmp_db.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundled_db, tmp_db)
    except Exception as exc:
        print(f"Vercel DB initialization warning: {exc}")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
app = application
