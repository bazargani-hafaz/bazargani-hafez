"""Railway Volume bootstrap for persistent store data.

When /data is mounted as a Railway Volume, move the existing local SQLite
store and uploaded product images into it on first boot, then transparently
map the application's existing paths to the persistent locations.
"""
from pathlib import Path
import shutil

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


def _link_persistent_path(local: Path, persistent: Path) -> None:
    persistent.parent.mkdir(parents=True, exist_ok=True)
    if local.is_symlink():
        try:
            if local.resolve() == persistent.resolve():
                return
        except OSError:
            pass
        local.unlink()
    elif local.exists():
        if local.is_dir():
            # Content is copied before this function is called.
            shutil.rmtree(local)
        else:
            local.unlink()
    local.symlink_to(persistent, target_is_directory=persistent.is_dir() or not persistent.suffix)


def bootstrap_volume() -> None:
    # No mounted Railway Volume: keep normal local development behaviour.
    if not VOLUME.exists() or not VOLUME.is_dir():
        return

    data_instance = VOLUME / "instance"
    data_uploads = VOLUME / "uploads"
    local_instance = BASE / "instance"
    local_uploads = BASE / "static" / "uploads"

    # First deployment: preserve any existing data before replacing local paths.
    data_instance.mkdir(parents=True, exist_ok=True)
    data_uploads.mkdir(parents=True, exist_ok=True)
    local_db = local_instance / "store.db"
    persistent_db = data_instance / "store.db"
    if local_db.exists() and not persistent_db.exists():
        shutil.copy2(local_db, persistent_db)
    _copy_tree_contents(local_uploads, data_uploads)

    # The application already uses BASE/instance/store.db and BASE/static/uploads.
    # Symlinks let the existing application use the persistent Volume without
    # changing every route that handles products and media.
    _link_persistent_path(local_instance, data_instance)
    local_uploads.parent.mkdir(parents=True, exist_ok=True)
    _link_persistent_path(local_uploads, data_uploads)


try:
    bootstrap_volume()
except Exception:
    # Never prevent the web process from starting because of a persistence
    # bootstrap problem. The application can still run using its normal paths.
    pass
