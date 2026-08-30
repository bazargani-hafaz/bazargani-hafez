import sqlite3
from flask import render_template, request, redirect, url_for, flash

def register_admin_19(app):
    def guard():
        from flask import session
        return session.get('admin') is True
    def db():
        from app import db as getdb
        return getdb()
    @app.route('/admin/products/quick/<int:pid>', methods=['POST'])
    def admin_product_quick(pid):
        if not guard(): return redirect(url_for('login', next=request.path))
        c=db(); p=c.execute('SELECT id FROM products WHERE id=?',(pid,)).fetchone()
        if not p: c.close(); return ('محصول پیدا نشد',404)
        price=request.form.get('price'); stock=request.form.get('stock'); active=request.form.get('active')
        if price is not None:
            try: price_n=float(price)
            except ValueError: price_n=None
            if price_n is not None: c.execute('UPDATE products SET price=? WHERE id=?',(price_n,pid))
        if stock is not None:
            try: stock_n=int(stock)
            except ValueError: stock_n=None
            if stock_n is not None: c.execute('UPDATE products SET stock=? WHERE id=?',(stock_n,pid))
        if active is not None: c.execute('UPDATE products SET active=? WHERE id=?',(1 if active in ('1','true','on') else 0,pid))
        c.commit(); c.close(); flash('تغییر سریع ذخیره شد.','success'); return redirect(url_for('admin_products'))
    @app.route('/admin/products/bulk', methods=['POST'])
    def admin_products_bulk():
        if not guard(): return redirect(url_for('login', next=request.path))
        ids=[]
        for x in request.form.getlist('product_ids'):
            try: ids.append(int(x))
            except ValueError: pass
        action=request.form.get('bulk_action','')
        if ids:
            marks=','.join('?' for _ in ids); c=db()
            if action=='activate': c.execute(f'UPDATE products SET active=1 WHERE id IN ({marks})',ids)
            elif action=='deactivate': c.execute(f'UPDATE products SET active=0 WHERE id IN ({marks})',ids)
            elif action=='delete': c.execute(f'DELETE FROM products WHERE id IN ({marks})',ids)
            elif action=='featured': c.execute(f'UPDATE products SET featured=1 WHERE id IN ({marks})',ids)
            elif action=='unfeatured': c.execute(f'UPDATE products SET featured=0 WHERE id IN ({marks})',ids)
            c.commit(); c.close(); flash(f'عملیات روی {len(ids)} محصول انجام شد.','success')
        return redirect(url_for('admin_products'))
    @app.route('/admin/homepage', methods=['GET','POST'])
    def admin_homepage():
        if not guard(): return redirect(url_for('login', next=request.path))
        c=db()
        if request.method=='POST':
            values={k:request.form.get(k,'') for k in ('hero_title','hero_text','home_show_hero','home_show_categories','home_show_collection','home_show_recent')}
            for k,v in values.items(): c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,v))
            c.commit(); flash('چیدمان صفحه اصلی ذخیره شد.','success')
        s={r['key']:r['value'] for r in c.execute('SELECT * FROM settings')}; c.close(); return render_template('admin_homepage.html',settings=s)
