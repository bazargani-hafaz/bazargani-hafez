# -*- coding: utf-8 -*-
"""Idempotent import of the 1405/03/03 price list. Source: 1779618128-1405-03-03.pdf. Prices are IRR consumer prices including 10% VAT."""
import re
PRICE_LIST_DATE = "1405/03/03"
RAW_PRODUCTS = 'REPLACE_ME'

def import_price_list(db):
    c = db()
    imported = updated = 0
    categories = {"DH":"هود","DG":"گاز","DS":"سینک","DF":"فر","DT":"فر"}
    slugs = {"هود":"hoods","گاز":"cookers","سینک":"sinks","فر":"ovens","تجهیزات آشپزخانه":"kitchen"}
    for name in set(categories.values()) | {"تجهیزات آشپزخانه"}:
        c.execute("INSERT OR IGNORE INTO categories(name,slug) VALUES(?,?)", (name, slugs[name]))
    cat_ids = {r["name"]: r["id"] for r in c.execute("SELECT id,name FROM categories").fetchall()}
    for line in RAW_PRODUCTS.splitlines():
        parts = line.split("|")
        if len(parts) != 4: continue
        name, model, color, price = [p.strip() for p in parts]
        if not price.isdigit(): continue
        model = re.sub(r"\\s+", "", model)
        price = float(price)
        category = categories.get(model[:2].upper(), "تجهیزات آشپزخانه") if model else "تجهیزات آشپزخانه"
        if not name: name = model or "محصول"
        sku = "PL-" + re.sub(r"[^0-9A-Za-z]+", "-", f"{PRICE_LIST_DATE}|{model}|{color}|{name}").strip("-")[:180]
        existing = c.execute("SELECT id FROM products WHERE sku=? LIMIT 1", (sku,)).fetchone()
        if not existing and model:
            existing = c.execute("SELECT id FROM products WHERE model=? AND color=? LIMIT 1", (model, color)).fetchone()
        desc = f"قیمت مصرف‌کننده بر اساس لیست {PRICE_LIST_DATE}؛ قیمت شامل ۱۰٪ مالیات بر ارزش افزوده است."
        if existing:
            c.execute('UPDATE products SET name=?,category_id=?,brand=?,model=?,sku=?,colors=?,color=?,price=?,sale_price=?,active=1,badge=?,description=? WHERE id=?',
                      (name,cat_ids[category],"حافظ",model,sku,color,color,price,price,f"لیست قیمت {PRICE_LIST_DATE}",desc,existing["id"]))
            updated += 1
        else:
            from app import unique_slug
            base = re.sub(r"[^\\w\\u0600-\\u06ff]+", "-", f"{name}-{model}-{color}", flags=re.UNICODE).strip("-") or sku.lower()
            slug = unique_slug(c, base)
            c.execute('INSERT INTO products (name,slug,category_id,brand,model,sku,colors,color,price,sale_price,stock,description,active,badge,new_product) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (name,slug,cat_ids[category],"حافظ",model,sku,color,color,price,price,0,desc,1,f"لیست قیمت {PRICE_LIST_DATE}",1))
            imported += 1
    c.commit()
    c.close()
    return imported, updated
