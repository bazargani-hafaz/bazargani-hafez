import os
import re
import sqlite3
import threading
import uuid
from html import unescape
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

SOURCE_SEARCH = "https://citysazeh.com/?s={query}&post_type=product"
USER_AGENT = "Mozilla/5.0 (compatible; HafezProductImageResolver/1.0)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(IMAGE_DIR, exist_ok=True)
_lock = threading.Lock()
_pending = set()
_workers_started = False
_queue = []
_queue_event = threading.Event()

PLACEHOLDER_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" viewBox="0 0 1 1"><rect width="1" height="1" fill="none"/></svg>'


def _get(url, timeout=6):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.6"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _download_image(url, timeout=8):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.6"})
    with urlopen(req, timeout=timeout) as r:
        data = r.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024:
            return None
        content_type = (r.headers.get("Content-Type") or "").lower()
    if not data:
        return None
    if "image/jpeg" in content_type or data.startswith(b"\xff\xd8\xff"):
        ext = "jpg"
    elif "image/png" in content_type or data.startswith(b"\x89PNG"):
        ext = "png"
    elif "image/webp" in content_type or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        ext = "webp"
    else:
        return None
    filename = f"remote_{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(IMAGE_DIR, filename), "wb") as f:
        f.write(data)
    return filename


def _first_product_url(html):
    links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    for link in links:
        link = unescape(link)
        if "/product/" in link and "citysazeh.com" in link:
            return link.split("#", 1)[0]
    return None


def _og_image(html):
    patterns = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, flags=re.I)
        if m:
            return unescape(m.group(1)).strip()
    return None


def resolve_product_image(product):
    model = (product["model"] or "").strip()
    color = (product["color"] or "").strip()
    name = (product["name"] or "").strip()
    queries = []
    if model and color:
        queries.append(f"{model} {color}")
    if model:
        queries.append(model)
    if name:
        queries.append(name)
    for query in queries:
        try:
            search_html = _get(SOURCE_SEARCH.format(query=quote_plus(query)))
            product_url = _first_product_url(search_html)
            if not product_url:
                continue
            page_html = _get(product_url)
            image = _og_image(page_html)
            if image:
                return urljoin(product_url, image)
        except Exception:
            continue
    return None


def _cache_external_image(db_path, product_id, image_url):
    try:
        filename = _download_image(image_url)
        if not filename:
            return None
        c = sqlite3.connect(db_path)
        c.execute("UPDATE products SET image=? WHERE id=?", (filename, product_id))
        c.commit()
        c.close()
        return filename
    except Exception:
        return None


def resolve_and_cache(db_path, product_id):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    p = c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    c.close()
    if not p:
        return None
    current = (p["image"] or "").strip()
    if current.startswith("http://") or current.startswith("https://"):
        return _cache_external_image(db_path, product_id, current) or current
    if current:
        return current
    image = resolve_product_image(p)
    if image:
        return _cache_external_image(db_path, product_id, image)
    return None


def _worker():
    while True:
        _queue_event.wait()
        while True:
            with _lock:
                if not _queue:
                    _queue_event.clear()
                    break
                db_path, product_id = _queue.pop(0)
            key = (db_path, product_id)
            try:
                resolve_and_cache(db_path, product_id)
            except Exception:
                pass
            finally:
                with _lock:
                    _pending.discard(key)


def _ensure_workers():
    global _workers_started
    with _lock:
        if _workers_started:
            return
        _workers_started = True
        for i in range(3):
            threading.Thread(target=_worker, daemon=True, name=f"product-image-worker-{i}").start()


def request_resolve_async(db_path, product_id):
    _ensure_workers()
    key = (db_path, int(product_id))
    with _lock:
        if key in _pending:
            return
        _pending.add(key)
        _queue.append(key)
        _queue_event.set()


def warm_missing_images(db_path):
    c = sqlite3.connect(db_path)
    rows = c.execute("SELECT id FROM products WHERE active=1 AND (image IS NULL OR image='' OR image LIKE 'http://%' OR image LIKE 'https://%')").fetchall()
    c.close()
    for (product_id,) in rows:
        request_resolve_async(db_path, product_id)


def start_warmup(db_path):
    threading.Thread(target=warm_missing_images, args=(db_path,), daemon=True, name="product-image-warmup").start()
