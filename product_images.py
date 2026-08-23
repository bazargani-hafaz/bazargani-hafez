import re
import sqlite3
import threading
from html import unescape
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

SOURCE_SEARCH = "https://citysazeh.com/?s={query}&post_type=product"
USER_AGENT = "Mozilla/5.0 (compatible; HafezProductImageResolver/1.0)"
_lock = threading.Lock()
_pending = set()

# Tiny valid SVG used while an exact product image is being resolved in the background.
PLACEHOLDER_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" viewBox="0 0 1 1"><rect width="1" height="1" fill="none"/></svg>'

def _get(url, timeout=8):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.6"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

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

def resolve_and_cache(db_path, product_id):
    with _lock:
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        p = c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not p:
            c.close(); return None
        current = (p["image"] or "").strip()
        if current.startswith("http://") or current.startswith("https://"):
            c.close(); return current
        image = resolve_product_image(p)
        if image:
            c.execute("UPDATE products SET image=? WHERE id=?", (image, product_id))
            c.commit()
        c.close()
        return image

def _background_resolve(db_path, product_id):
    try:
        resolve_and_cache(db_path, product_id)
    finally:
        with _lock:
            _pending.discard((db_path, product_id))

def request_resolve_async(db_path, product_id):
    key = (db_path, int(product_id))
    with _lock:
        if key in _pending:
            return
        _pending.add(key)
    threading.Thread(target=_background_resolve, args=key, daemon=True, name=f"product-image-{product_id}").start()

def warm_missing_images(db_path):
    c = sqlite3.connect(db_path)
    ids = [r[0] for r in c.execute("SELECT id FROM products WHERE (image IS NULL OR image='') AND active=1").fetchall()]
    c.close()
    # Queue resolutions without blocking Flask's request workers.
    for product_id in ids:
        request_resolve_async(db_path, product_id)

def start_warmup(db_path):
    threading.Thread(target=warm_missing_images, args=(db_path,), daemon=True, name="product-image-warmup").start()
