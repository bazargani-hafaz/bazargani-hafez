"""Railway bootstrap, persistent storage, catalog import and security hooks."""
from pathlib import Path
import shutil
import os
import sqlite3
import threading
import time

BASE = Path(__file__).resolve().parent
VOLUME = Path("/data")


def _copy_tree_contents(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if target.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def _ensure_link(local: Path, persistent: Path) -> None:
    persistent.parent.mkdir(parents=True, exist_ok=True)
    if local.is_symlink():
        try:
            if local.resolve() == persistent.resolve():
                return
        except OSError:
            local.unlink()
        else:
            local.unlink()
    elif local.exists():
        if local.is_dir():
            shutil.rmtree(local)
        else:
            local.unlink()
    local.symlink_to(persistent, target_is_directory=True)


def bootstrap_volume() -> None:
    if not VOLUME.is_dir():
        return

    data_instance = VOLUME / "instance"
    data_uploads = VOLUME / "uploads"
    local_instance = BASE / "instance"
    local_uploads = BASE / "static" / "uploads"

    data_instance.mkdir(parents=True, exist_ok=True)
    data_uploads.mkdir(parents=True, exist_ok=True)

    local_db = local_instance / "store.db"
    persistent_db = data_instance / "store.db"
    if local_db.exists() and not persistent_db.exists():
        shutil.copy2(local_db, persistent_db)
    _copy_tree_contents(local_uploads, data_uploads)

    _ensure_link(local_instance, data_instance)
    local_uploads.parent.mkdir(parents=True, exist_ok=True)
    _ensure_link(local_uploads, data_uploads)

    if not local_db.parent.is_symlink() or local_db.parent.resolve() != data_instance.resolve():
        raise RuntimeError("Railway persistence setup failed: instance is not backed by /data")
    if not local_uploads.is_symlink() or local_uploads.resolve() != data_uploads.resolve():
        raise RuntimeError("Railway persistence setup failed: uploads are not backed by /data")


def cleanup_catalog_once() -> None:
    if os.getenv("CLEANUP_PRODUCTS") != "1":
        return
    db_path = VOLUME / "instance" / "store.db"
    if db_path.exists():
        c = sqlite3.connect(db_path)
        try:
            c.execute("DELETE FROM products")
            c.commit()
        finally:
            c.close()
    uploads = VOLUME / "uploads"
    if uploads.is_dir():
        for item in uploads.iterdir():
            if item.is_file() or item.is_symlink():
                try:
                    item.unlink()
                except OSError:
                    pass


bootstrap_volume()
cleanup_catalog_once()

# Import the Dorsa 1405/03/03 price list after the Flask app has initialized its schema.
# This is deliberately asynchronous so it cannot block Railway's web startup.
def _import_dorsa_catalog() -> None:
    for _ in range(30):
        try:
            import app
            from price_list_seed import import_price_list
            imported, updated = import_price_list(app.db)
            print(f"[hafez] Dorsa price-list sync complete: imported={imported}, updated={updated}")
            try:
                app.start_warmup(str(app.DB))
            except Exception as exc:
                print(f"[hafez] image warmup start warning: {exc}")
            return
        except Exception as exc:
            time.sleep(1)
    print("[hafez] Dorsa price-list sync did not complete during startup")

threading.Thread(target=_import_dorsa_catalog, daemon=True, name="dorsa-catalog-import").start()

# Install security hooks without requiring changes to the application's route code.
try:
    from flask import Flask
    from security import init_security
    _original_flask_init = Flask.__init__

    def _secure_flask_init(self, *args, **kwargs):
        _original_flask_init(self, *args, **kwargs)
        init_security(self)

    if not getattr(Flask.__init__, "_hafez_security_wrapped", False):
        _secure_flask_init._hafez_security_wrapped = True
        Flask.__init__ = _secure_flask_init
except ImportError:
    pass
