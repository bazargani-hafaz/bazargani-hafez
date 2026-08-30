import os, sqlite3
from urllib.parse import quote
from flask import render_template, request, jsonify

def register_enhancements(app):
    db_path=os.path.join(app.root_path,'instance','store.db')
    original_products=app.view_functions.get('products')
    if original_products:
        def products_enhanced():
            q=request.args.get('q','').strip();cat=request.args.get('cat','').strip();brand=request.args.get('brand','').strip();stock=request.args.get('stock','').strip();sort=request.args.get('sort','featured').strip();min_price=request.args.get('min_price','').strip();max_price=request.args.get('max_price','').strip()
            try:min_price_n=float(min_price) if min_price else None
            except ValueError:min_price_n=None
            try:max_price_n=float(max_price) if max_price else None
            except ValueError:max_price_n=None
            c=sqlite3.connect(db_path);c.row_factory=sqlite3.Row;sql='SELECT p.*,c.name category,c.slug catslug FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1';a=[]
            if q:sql+=' AND (p.name LIKE ? OR p.brand LIKE ? OR p.model LIKE ? OR p.sku LIKE ? OR p.description LIKE ? OR p.short_description LIKE ?)';a += [f'%{q}%']*6
            if cat:sql+=' AND c.slug=?';a.append(cat)
            if brand:sql+=' AND p.brand=?';a.append(brand)
            if stock=='available':sql+=' AND p.stock>0'
            elif stock=='out':sql+=' AND p.stock<=0'
            pe='COALESCE(NULLIF(p.sale_price,0),p.price)'
            if min_price_n is not None:sql+=f' AND {pe}>=?';a.append(min_price_n)
            if max_price_n is not None:sql+=f' AND {pe}<=?';a.append(max_price_n)
            order={'price_asc':f'{pe} ASC,p.id DESC','price_desc':f'{pe} DESC,p.id DESC','name':'p.name COLLATE NOCASE ASC','newest':'p.id DESC','featured':'p.featured DESC,p.bestseller DESC,p.id DESC'}.get(sort,'p.featured DESC,p.bestseller DESC,p.id DESC')
            rows=c.execute(sql+' ORDER BY '+order,a).fetchall();brands=[r['brand'] for r in c.execute("SELECT DISTINCT brand FROM products WHERE active=1 AND brand<>'' ORDER BY brand").fetchall()];c.close();return render_template('products.html',products=rows,q=q,selected=cat,selected_brand=brand,stock_filter=stock,sort=sort,min_price=min_price,max_price=max_price,brands=brands)
        app.view_functions['products']=products_enhanced
    original_product=app.view_functions.get('product')
    if original_product:
        def product_enhanced(slug):
            c=sqlite3.connect(db_path);c.row_factory=sqlite3.Row;p=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.slug=? AND p.active=1',(slug,)).fetchone()
            if not p:c.close();return original_product(slug)
            related=c.execute("SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.id<>? AND (p.category_id=? OR (p.brand<>'' AND p.brand=?)) ORDER BY (p.category_id=?) DESC,p.featured DESC,p.id DESC LIMIT 6",(p['id'],p['category_id'],p['brand'],p['category_id'])).fetchall()
            if len(related)<6:
                existing={r['id'] for r in related};extra=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.id<>? ORDER BY p.featured DESC,p.id DESC LIMIT 12',(p['id'],)).fetchall();related=related+[r for r in extra if r['id'] not in existing][:6-len(related)]
            c.close();return render_template('product.html',product=p,related_products=related)
        app.view_functions['product']=product_enhanced
    @app.route('/compare')
    def compare():
        raw=request.args.get('ids','');ids=[]
        for x in raw.split(','):
            try:
                n=int(x)
                if n>0 and n not in ids:ids.append(n)
            except ValueError:pass
        ids=ids[:4];c=sqlite3.connect(db_path);c.row_factory=sqlite3.Row;products=[]
        if ids:
            ph=','.join('?' for _ in ids);rows=c.execute(f'SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.id IN ({ph})',ids).fetchall();byid={p['id']:p for p in rows};products=[byid[i] for i in ids if i in byid]
        c.close();return render_template('compare.html',products=products)
    @app.template_global('whatsapp_url')
    def whatsapp_url(product):
        c=sqlite3.connect(db_path);row=c.execute("SELECT value FROM settings WHERE key='phone'").fetchone();c.close();phone=''.join(ch for ch in (row[0] if row else '') if ch.isdigit())
        if phone.startswith('0'):phone='98'+phone[1:]
        text=quote(f'سلام، درباره محصول «{product["name"]}» درخواست استعلام قیمت و موجودی دارم.')
        return f'https://wa.me/{phone}?text={text}' if phone else f'https://wa.me/?text={text}'
    @app.route('/api/product-by-slug')
    def product_by_slug():
        slug=request.args.get('slug','').strip();c=sqlite3.connect(db_path);c.row_factory=sqlite3.Row;p=c.execute('SELECT id,name,slug,price,sale_price FROM products WHERE slug=? AND active=1',(slug,)).fetchone();c.close();return jsonify(dict(p)) if p else ('',404)
    @app.route('/api/home-config')
    def home_config():
        c=sqlite3.connect(db_path);rows=c.execute("SELECT key,value FROM settings WHERE key LIKE 'home_show_%'").fetchall();c.close();return jsonify({k:v for k,v in rows})
    @app.route('/api/price-alert',methods=['POST'])
    def price_alert():
        data=request.get_json(silent=True) or {};pid=int(data.get('product_id') or 0);c=sqlite3.connect(db_path);c.execute('CREATE TABLE IF NOT EXISTS price_alerts(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL,contact TEXT DEFAULT "",created_at TEXT DEFAULT CURRENT_TIMESTAMP)');exists=c.execute('SELECT id FROM price_alerts WHERE product_id=? AND contact=?',(pid,request.remote_addr or '')).fetchone()
        if not exists:c.execute('INSERT INTO price_alerts(product_id,contact) VALUES(?,?)',(pid,request.remote_addr or ''));c.commit()
        c.close();return jsonify({'ok':True,'message':'اعلان تغییر قیمت برای این محصول ثبت شد.'})
    @app.route('/wishlist')
    def wishlist():return render_template('wishlist.html')
