"""Complete admin CRUD routes loaded by the security layer."""
from pathlib import Path
import json
import shutil
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort, send_file
from werkzeug.utils import secure_filename


def register_admin_routes(app):
    def deps():
        from app import db, admin, save_image, UP, unique_slug, slugify, DB
        return db, admin, save_image, UP, unique_slug, slugify, DB

    @app.route('/admin/products', methods=['GET', 'POST'])
    def admin_products():
        db, admin, save_image, UP, unique_slug, slugify, DB = deps()
        if request.method == 'POST':
            if not _is_admin():
                return redirect(url_for('login', next=request.path))
            name = request.form.get('name', '').strip()
            if not name:
                flash('نام محصول الزامی است.', 'error')
                return redirect(url_for('admin_products'))
            c = db()
            try:
                slug = unique_slug(c, name)
                category_id = request.form.get('category_id') or None
                image = ''
                gallery = []
                primary = request.files.get('image')
                if primary and primary.filename:
                    image = save_image(primary)
                for f in request.files.getlist('gallery_images'):
                    if f and f.filename:
                        gallery.append(save_image(f))
                colors = request.form.get('colors', '').strip()
                price = 0
                for line in colors.splitlines():
                    if '|' in line:
                        try: price = float(line.split('|', 1)[1].strip().replace(',', ''))
                        except ValueError: pass
                c.execute('''INSERT INTO products(name,slug,category_id,brand,model,sku,colors,price,stock,material,warranty,image,gallery,description,active) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)''', (name, slug, category_id, request.form.get('brand','').strip(), request.form.get('model','').strip(), request.form.get('sku','').strip(), colors, price, int(request.form.get('stock') or 0), request.form.get('material','').strip(), request.form.get('warranty','').strip(), image, ','.join(gallery), request.form.get('description','').strip()))
                c.commit(); flash('محصول با موفقیت اضافه شد.', 'success')
            except Exception:
                c.rollback(); raise
            finally: c.close()
            return redirect(url_for('admin_products'))
        c = db(); products = c.execute('SELECT p.*, c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC').fetchall(); cats = c.execute('SELECT * FROM categories ORDER BY name').fetchall(); c.close()
        return render_template('manage_products.html', products=products, categories=cats)

    @app.route('/admin/products/edit/<int:pid>', methods=['GET', 'POST'])
    def admin_product_edit(pid):
        db, admin, save_image, UP, unique_slug, slugify, DB = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        c = db(); p = c.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
        if not p: c.close(); abort(404)
        if request.method == 'POST':
            name = request.form.get('name', '').strip() or p['name']; image = p['image']; gallery = p['gallery'] or ''
            primary = request.files.get('image')
            if primary and primary.filename: image = save_image(primary)
            gs = [save_image(f) for f in request.files.getlist('gallery_images') if f and f.filename]
            if gs: gallery = ','.join(([x.strip() for x in gallery.split(',') if x.strip()] + gs))
            c.execute('''UPDATE products SET name=?,slug=?,category_id=?,brand=?,model=?,sku=?,colors=?,stock=?,material=?,warranty=?,image=?,gallery=? WHERE id=?''', (name, unique_slug(c, name, pid), request.form.get('category_id') or None, request.form.get('brand','').strip(), request.form.get('model','').strip(), request.form.get('sku','').strip(), request.form.get('colors','').strip(), int(request.form.get('stock') or 0), request.form.get('material','').strip(), request.form.get('warranty','').strip(), image, gallery, pid))
            c.commit(); c.close(); flash('محصول ویرایش شد.', 'success'); return redirect(url_for('admin_products'))
        cats = c.execute('SELECT * FROM categories ORDER BY name').fetchall(); c.close(); return render_template('product_form.html', p=p, cats=cats)

    @app.route('/admin/products/delete/<int:pid>', methods=['POST'])
    def admin_product_delete(pid):
        db, *_ = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        c=db(); c.execute('DELETE FROM products WHERE id=?',(pid,)); c.commit(); c.close(); flash('محصول حذف شد.','success'); return redirect(url_for('admin_products'))

    @app.route('/admin/categories', methods=['GET','POST'])
    def admin_categories():
        db,*_ = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        c=db()
        if request.method=='POST':
            name=request.form.get('name','').strip(); slug=request.form.get('slug','').strip() or slugify(name)
            if name: c.execute('INSERT OR IGNORE INTO categories(name,slug) VALUES(?,?)',(name,slug)); c.commit(); flash('دسته‌بندی اضافه شد.','success')
            c.close(); return redirect(url_for('admin_categories'))
        rows=c.execute('SELECT c.*,COUNT(p.id) product_count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id ORDER BY c.name').fetchall(); c.close(); return render_template('admin_categories.html',categories=rows)

    @app.route('/admin/categories/delete/<int:cid>', methods=['POST'])
    def admin_category_delete(cid):
        db,*_ = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        c=db(); c.execute('UPDATE products SET category_id=NULL WHERE category_id=?',(cid,)); c.execute('DELETE FROM categories WHERE id=?',(cid,)); c.commit(); c.close(); flash('دسته‌بندی حذف شد.','success'); return redirect(url_for('admin_categories'))

    @app.route('/admin/media', methods=['GET','POST'])
    def admin_media():
        db, admin, save_image, UP, *_ = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        if request.method=='POST':
            f=request.files.get('image')
            if f and f.filename:
                save_image(f); flash('تصویر آپلود شد.','success')
            return redirect(url_for('admin_media'))
        files=[]
        for p in sorted(UP.iterdir(), key=lambda x:x.stat().st_mtime, reverse=True):
            if p.is_file(): files.append({'name':p.name,'size':p.stat().st_size,'mtime':datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})
        return render_template('admin_media.html',files=files)

    @app.route('/admin/media/delete/<path:name>', methods=['POST'])
    def admin_media_delete(name):
        db,*_ ,UP, *_rest = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        p=(UP/secure_filename(name)).resolve()
        if p.parent == UP.resolve() and p.exists(): p.unlink()
        return redirect(url_for('admin_media'))

    @app.route('/admin/system')
    def admin_system():
        db, *_ = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        c=db(); data={'products':c.execute('SELECT COUNT(*) n FROM products').fetchone()['n'],'categories':c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n'],'settings':c.execute('SELECT COUNT(*) n FROM settings').fetchone()['n']}; c.close()
        from app import UP, DB
        data['uploads_count']=sum(1 for p in UP.iterdir() if p.is_file()); data['uploads_size']=sum(p.stat().st_size for p in UP.iterdir() if p.is_file()); data['database_size']=DB.stat().st_size if DB.exists() else 0
        return render_template('admin_system.html',data=data)

    @app.route('/admin/backup')
    def admin_backup():
        db,*_ ,DB = deps()
        if not _is_admin(): return redirect(url_for('login', next=request.path))
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); return send_file(DB, as_attachment=True, download_name=f'hafez-backup-{stamp}.db')


def _is_admin():
    from flask import session
    return session.get('admin') is True
