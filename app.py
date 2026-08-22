import os, sqlite3, uuid, shutil, json, re, time
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, send_from_directory, make_response
from werkzeug.utils import secure_filename

BASE=Path(__file__).resolve().parent
DB=Path('/data')/f'store.db'
UP=Path('/data')/'uploads'
UP.mkdir(parents=True,exist_ok=True)
Path('/data').mkdir(parents=True,exist_ok=True)

SECRET_KEY=os.getenv('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY=uuid.uuid4().hex+uuid.uuid4().hex

app=Flask(__name__)
app.secret_key=SECRET_KEY
app.config.update(
    MAX_CONTENT_LENGTH=10*1024*1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','1').lower() in ('1','true','yes'),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UP, filename)

ALLOWED_IMAGE_EXT={'jpg','jpeg','png','webp'}
ALLOWED_IMAGE_TYPES={'jpg':b'\xff\xd8\xff','jpeg':b'\xff\xd8\xff','png':b'\x89PNG\r\n\x1a\n','webp':b'RIFF'}
LOGIN_WINDOW=300
LOGIN_LIMIT=8
_login_attempts={}


def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c


def slugify(text):
    text=(text or '').strip().lower()
    text=re.sub(r'[^\w\u0600-\u06ff\s-]','',text,flags=re.UNICODE)
    text=re.sub(r'[\s_-]+','-',text).strip('-')
    return text or uuid.uuid4().hex[:10]


def unique_slug(c,name,pid=None):
    base=slugify(name); slug=base; i=2
    while True:
        q='SELECT id FROM products WHERE slug=?'; a=[slug]
        if pid is not None: q+=' AND id<>?'; a.append(pid)
        if not c.execute(q,a).fetchone(): return slug
        slug=f'{base}-{i}'; i+=1


def init_db():
    c=db(); c.executescript('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL);CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL,category_id INTEGER,brand TEXT DEFAULT '',model TEXT DEFAULT '',sku TEXT DEFAULT '',short_description TEXT DEFAULT '',description TEXT DEFAULT '',specs TEXT DEFAULT '',price REAL DEFAULT 0,sale_price REAL DEFAULT 0,stock INTEGER DEFAULT 0,color TEXT DEFAULT '',colors TEXT DEFAULT '',material TEXT DEFAULT '',finish TEXT DEFAULT '',length TEXT DEFAULT '',width TEXT DEFAULT '',height TEXT DEFAULT '',weight TEXT DEFAULT '',package_dimensions TEXT DEFAULT '',package_weight TEXT DEFAULT '',warranty TEXT DEFAULT '',warranty_company TEXT DEFAULT '',shipping_time TEXT DEFAULT '',shipping_cost REAL DEFAULT 0,free_shipping INTEGER DEFAULT 0,seo_title TEXT DEFAULT '',seo_description TEXT DEFAULT '',seo_keywords TEXT DEFAULT '',badge TEXT DEFAULT '',featured INTEGER DEFAULT 0,new_product INTEGER DEFAULT 0,bestseller INTEGER DEFAULT 0,active INTEGER DEFAULT 1,image TEXT DEFAULT '',gallery TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
    for k,v in {'site_name':'فروشگاه حافظ','tagline':'ویترین آنلاین محصولات','phone':'09120000000','address':'تهران','hero_title':'انتخابی حرفه‌ای برای خانه شما','hero_text':'محصولات منتخب را در ویترین حافظ ببینید.'}.items(): c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,v))
    if c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n']==0:
        for n,s in [('شیرآلات','faucets'),('سینک','sinks'),('گاز','cookers'),('هود','hoods'),('تجهیزات آشپزخانه','kitchen')]: c.execute('INSERT INTO categories(name,slug) VALUES(?,?)',(n,s))
    c.commit(); c.close()


def migrate():
    c=db(); cols={r['name'] for r in c.execute('PRAGMA table_info(products)')}; additions={'model':'TEXT DEFAULT ""','sku':'TEXT DEFAULT ""','short_description':'TEXT DEFAULT ""','price':'REAL DEFAULT 0','sale_price':'REAL DEFAULT 0','stock':'INTEGER DEFAULT 0','color':'TEXT DEFAULT ""','colors':'TEXT DEFAULT ""','material':'TEXT DEFAULT ""','finish':'TEXT DEFAULT ""','length':'TEXT DEFAULT ""','width':'TEXT DEFAULT ""','height':'TEXT DEFAULT ""','weight':'TEXT DEFAULT ""','package_dimensions':'TEXT DEFAULT ""','package_weight':'TEXT DEFAULT ""','warranty':'TEXT DEFAULT ""','warranty_company':'TEXT DEFAULT ""','shipping_time':'TEXT DEFAULT ""','shipping_cost':'REAL DEFAULT 0','free_shipping':'INTEGER DEFAULT 0','seo_title':'TEXT DEFAULT ""','seo_description':'TEXT DEFAULT ""','seo_keywords':'TEXT DEFAULT ""','badge':'TEXT DEFAULT ""','new_product':'INTEGER DEFAULT 0','bestseller':'INTEGER DEFAULT 0','gallery':'TEXT DEFAULT ""'}
    for k,v in additions.items():
        if k not in cols: c.execute(f'ALTER TABLE products ADD COLUMN {k} {v}')
    c.commit(); c.close()


def client_key():
    return request.headers.get('X-Forwarded-For',request.remote_addr or 'unknown').split(',')[0].strip()


def rate_limited(key):
    now=time.time(); arr=[t for t in _login_attempts.get(key,[]) if now-t<LOGIN_WINDOW]; _login_attempts[key]=arr
    return len(arr)>=LOGIN_LIMIT


def record_login_failure(key):
    _login_attempts.setdefault(key,[]).append(time.time())


def clear_login_failures(key):
    _login_attempts.pop(key,None)


def valid_image(file):
    if not file or not file.filename: return False
    name=secure_filename(file.filename); ext=name.rsplit('.',1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_IMAGE_EXT: return False
    head=file.stream.read(12); file.stream.seek(0)
    if ext in ('jpg','jpeg','png') and not head.startswith(ALLOWED_IMAGE_TYPES[ext]): return False
    if ext=='webp' and not (head.startswith(b'RIFF') and head[8:12]==b'WEBP'): return False
    return True


def save_image(file):
    if not valid_image(file): raise ValueError('فرمت تصویر مجاز نیست.')
    name=secure_filename(file.filename); ext=name.rsplit('.',1)[-1].lower(); stem=secure_filename(name.rsplit('.',1)[0]) or 'product'
    fn=f'{stem}_{uuid.uuid4().hex[:12]}.{ext}'
    file.save(UP/fn)
    return fn


def safe_next(value):
    if not value or not value.startswith('/') or value.startswith('//'): return url_for('admin_home')
    return value


init_db(); migrate()

@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options','nosniff')
    response.headers.setdefault('X-Frame-Options','SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy','camera=(), microphone=(), geolocation=()')
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security','max-age=31536000; includeSubDomains')
    return response

@app.before_request
def protect_admin_requests():
    if request.path.startswith('/admin/') and request.method in {'POST','PUT','PATCH','DELETE'}:
        origin=request.headers.get('Origin')
        referer=request.headers.get('Referer')
        host=request.host_url.rstrip('/')
        if origin and origin.rstrip('/')!=host: abort(403)
        if not origin and referer and not referer.startswith(host+'/'): abort(403)

@app.context_processor
def ctx():
    c=db(); cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall(); c.close(); c2=db(); s={r['key']:r['value'] for r in c2.execute('SELECT * FROM settings')}; c2.close(); return {'settings':s,'nav_categories':cats}

def admin(f):
    @wraps(f)
    def w(*a,**k): return f(*a,**k) if session.get('admin') is True else redirect(url_for('login',next=request.path))
    return w

@app.route('/')
def home():
    c=db(); p=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 ORDER BY p.featured DESC,p.bestseller DESC,p.id DESC LIMIT 12').fetchall(); cats=c.execute('SELECT c.*,COUNT(p.id) count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id').fetchall(); c.close(); return render_template('index.html',products=p,categories=cats)

@app.route('/products')
def products():
    q=request.args.get('q','').strip(); cat=request.args.get('cat',''); c=db(); sql='SELECT p.*,c.name category,c.slug catslug FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1'; a=[]
    if q: sql+=' AND (p.name LIKE ? OR p.brand LIKE ? OR p.model LIKE ? OR p.sku LIKE ? OR p.description LIKE ?)'; a += [f'%{q}%']*5
    if cat: sql+=' AND c.slug=?'; a.append(cat)
    rows=c.execute(sql+' ORDER BY p.featured DESC,p.bestseller DESC,p.id DESC',a).fetchall(); c.close(); return render_template('products.html',products=rows,q=q,selected=cat)

@app.route('/product/<slug>')
def product(slug):
    c=db(); p=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.slug=? AND p.active=1',(slug,)).fetchone(); c.close(); return render_template('product.html',product=p) if p else abort(404)

@app.route('/admin/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        key=client_key()
        if rate_limited(key):
            flash('تعداد تلاش‌های ورود زیاد است. چند دقیقه بعد دوباره تلاش کنید.','error'); return render_template('login.html'),429
        username=os.getenv('ADMIN_USERNAME'); password=os.getenv('ADMIN_PASSWORD')
        if username and password and request.form.get('username')==username and request.form.get('password')==password:
            clear_login_failures(key); session.clear(); session.permanent=True; session['admin']=True; return redirect(safe_next(request.args.get('next')))
        record_login_failure(key); flash('نام کاربری یا رمز عبور اشتباه است.','error')
    return render_template('login.html')

@app.route('/admin/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/admin')
@admin
def admin_home():
    c=db(); counts={k:c.execute(q).fetchone()['n'] for k,q in {'products':'SELECT COUNT(*) n FROM products','categories':'SELECT COUNT(*) n FROM categories','featured':'SELECT COUNT(*) n FROM products WHERE featured=1'}.items()}; c.close(); return render_template('admin.html',counts=counts)

@app.route('/admin/products',methods=['GET','POST'])
@admin
def admin_products():
    c=db(); cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall()
    if request.method=='POST':
        try:
            uploaded=[]
            for f in request.files.getlist('image'):
                if f and f.filename: uploaded.append(save_image(f))
            img=uploaded[0] if uploaded else ''; gallery_names=uploaded[1:]
            manual_gallery=[x.strip() for x in request.form.get('gallery','').split(',') if x.strip() and Path(x).name==x]
            gallery=','.join(gallery_names+manual_gallery); name=request.form.get('name','').strip()
            if not name: flash('نام محصول الزامی است.','error'); return redirect(url_for('admin_products'))
            fields=['name','category_id','brand','model','sku','short_description','description','specs','price','sale_price','stock','color','colors','material','finish','length','width','height','weight','package_dimensions','package_weight','warranty','warranty_company','shipping_time','shipping_cost','seo_title','seo_description','seo_keywords','badge']
            vals=[request.form.get(x,'') for x in fields]; vals[1]=request.form.get('category_id') or None
            for i in [8,9,10,25]:
                try: vals[i]=float(vals[i] or 0) if i in [8,9,25] else int(vals[i] or 0)
                except (ValueError,TypeError): vals[i]=0
            flags=[1 if request.form.get(x) else 0 for x in ['free_shipping','featured','new_product','bestseller']]; slug=unique_slug(c,name)
            columns=['slug']+fields+['free_shipping','featured','new_product','bestseller','image','gallery']; values=[slug]+vals+flags+[img,gallery]
            c.execute('INSERT INTO products('+','.join(columns)+') VALUES('+','.join('?' for _ in values)+')',values); c.commit(); flash(f'محصول با موفقیت اضافه شد؛ {len(uploaded)} تصویر ذخیره شد.','ok')
        except ValueError as e: c.rollback(); flash(str(e),'error')
        except Exception: c.rollback(); flash('خطا در ذخیره محصول.','error')
    rows=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC').fetchall(); c.close(); return render_template('manage_products.html',products=rows,categories=cats)

@app.route('/admin/products/edit/<int:pid>',methods=['GET','POST'])
@admin
def edit_product(pid):
    c=db(); cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall(); p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
    if not p: c.close(); abort(404)
    if request.method=='POST':
        try:
            uploaded=[]
            for f in request.files.getlist('image'):
                if f and f.filename: uploaded.append(save_image(f))
            current_gallery=[x.strip() for x in (p['gallery'] or '').split(',') if x.strip() and Path(x).name==x]
            gallery_names=uploaded[1:] if uploaded else current_gallery; main_image=uploaded[0] if uploaded else (p['image'] or (current_gallery[0] if current_gallery else ''))
            manual_gallery=[x.strip() for x in request.form.get('gallery','').split(',') if x.strip() and Path(x).name==x]; gallery=','.join(gallery_names+manual_gallery)
            fields=['name','category_id','brand','model','sku','short_description','description','specs','price','sale_price','stock','color','colors','material','finish','length','width','height','weight','package_dimensions','package_weight','warranty','warranty_company','shipping_time','shipping_cost','seo_title','seo_description','seo_keywords','badge','gallery']; vals=[request.form.get(x,'') for x in fields]; vals[1]=request.form.get('category_id') or None
            for i in [8,9,10,26]:
                try: vals[i]=float(vals[i] or 0) if i in [8,9,26] else int(vals[i] or 0)
                except (ValueError,TypeError): vals[i]=0
            vals[-1]=gallery; flags=[1 if request.form.get(x) else 0 for x in ['free_shipping','featured','new_product','bestseller']]
            sets=','.join(f'{x}=?' for x in fields)+',free_shipping=?,featured=?,new_product=?,bestseller=?,slug=?,image=?'; vals += flags+[unique_slug(c,request.form.get('name',''),pid),main_image]
            c.execute('UPDATE products SET '+sets+' WHERE id=?',vals+[pid]); c.commit(); flash('محصول ویرایش شد.','ok'); return redirect(url_for('admin_products'))
        except ValueError as e: c.rollback(); flash(str(e),'error')
        except Exception: c.rollback(); flash('خطا در ویرایش محصول.','error')
    c.close(); return render_template('edit_product.html',product=p,categories=cats)

@app.post('/admin/products/delete/<int:pid>')
@admin
def delete_product(pid):
    c=db(); row=c.execute('SELECT image,gallery FROM products WHERE id=?',(pid,)).fetchone(); c.execute('DELETE FROM products WHERE id=?',(pid,)); c.commit(); c.close()
    if row:
        for fn in [row['image']]+[x.strip() for x in (row['gallery'] or '').split(',') if x.strip()]:
            if fn and Path(fn).name==fn:
                try:(UP/fn).unlink(missing_ok=True)
                except OSError: pass
    return redirect(url_for('admin_products'))

@app.route('/admin/settings',methods=['GET','POST'])
@admin
def admin_settings():
    if request.method=='POST':
        c=db()
        for k in ['site_name','tagline','phone','address','hero_title','hero_text']: c.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,request.form.get(k,'')))
        c.commit(); c.close(); flash('تنظیمات ذخیره شد.','ok')
    return render_template('settings.html')

@app.route('/admin/categories',methods=['GET','POST'])
@admin
def admin_categories():
    c=db()
    if request.method=='POST':
        name=request.form.get('name','').strip(); slug=secure_filename(request.form.get('slug','').strip()) or uuid.uuid4().hex[:10]
        if name:
            try:c.execute('INSERT INTO categories(name,slug) VALUES(?,?)',(name,slug));c.commit();flash('دسته‌بندی ساخته شد.','ok')
            except sqlite3.IntegrityError:flash('Slug تکراری است.','error')
    rows=c.execute('SELECT c.*,COUNT(p.id) product_count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id ORDER BY c.id DESC').fetchall(); c.close(); return render_template('admin_categories.html',categories=rows)

@app.post('/admin/categories/delete/<int:cid>')
@admin
def delete_category(cid):
    c=db();c.execute('UPDATE products SET category_id=NULL WHERE category_id=?',(cid,));c.execute('DELETE FROM categories WHERE id=?',(cid,));c.commit();c.close();return redirect(url_for('admin_categories'))

@app.route('/admin/media',methods=['GET','POST'])
@admin
def admin_media():
    if request.method=='POST':
        f=request.files.get('image')
        try:
            if f and f.filename: save_image(f); flash('تصویر آپلود شد.','ok')
        except ValueError as e: flash(str(e),'error')
    files=[{'name':p.name,'size':p.stat().st_size,'mtime':datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')} for p in sorted(UP.iterdir(),key=lambda x:x.stat().st_mtime,reverse=True) if p.is_file()] if UP.exists() else [];return render_template('admin_media.html',files=files)

@app.post('/admin/media/delete/<name>')
@admin
def delete_media(name):
    safe=secure_filename(name); p=(UP/safe).resolve()
    if safe==name and p.parent==UP.resolve() and p.is_file():p.unlink()
    return redirect(url_for('admin_media'))

@app.route('/admin/system')
@admin
def admin_system():
    c=db();data={'products':c.execute('SELECT COUNT(*) n FROM products').fetchone()['n'],'categories':c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n'],'settings':c.execute('SELECT COUNT(*) n FROM settings').fetchone()['n']};c.close();data.update({'database_size':DB.stat().st_size if DB.exists() else 0,'uploads_count':len([p for p in UP.iterdir() if p.is_file()]),'uploads_size':sum(p.stat().st_size for p in UP.iterdir() if p.is_file())});return render_template('admin_system.html',data=data)

@app.route('/admin/backup')
@admin
def admin_backup():
    backup=Path('/data')/f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db';shutil.copy2(DB,backup)
    try: return send_file(backup,as_attachment=True,download_name=backup.name)
    finally:
        try: backup.unlink(missing_ok=True)
        except OSError: pass

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)))
