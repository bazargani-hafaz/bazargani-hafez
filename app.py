import os, sqlite3, uuid, shutil, json
from pathlib import Path
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file
from werkzeug.utils import secure_filename
BASE=Path(__file__).resolve().parent; DB=BASE/'instance/store.db'; UP=BASE/'static/uploads'; UP.mkdir(parents=True,exist_ok=True); DB.parent.mkdir(parents=True,exist_ok=True)
app=Flask(__name__); app.secret_key=os.getenv('SECRET_KEY','change-me'); app.config['MAX_CONTENT_LENGTH']=12*1024*1024

def db(): c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
 c=db(); c.executescript('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL);CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL,category_id INTEGER,brand TEXT DEFAULT '',model TEXT DEFAULT '',sku TEXT DEFAULT '',short_description TEXT DEFAULT '',description TEXT DEFAULT '',specs TEXT DEFAULT '',price REAL DEFAULT 0,sale_price REAL DEFAULT 0,stock INTEGER DEFAULT 0,color TEXT DEFAULT '',colors TEXT DEFAULT '',material TEXT DEFAULT '',finish TEXT DEFAULT '',length TEXT DEFAULT '',width TEXT DEFAULT '',height TEXT DEFAULT '',weight TEXT DEFAULT '',package_dimensions TEXT DEFAULT '',package_weight TEXT DEFAULT '',warranty TEXT DEFAULT '',warranty_company TEXT DEFAULT '',shipping_time TEXT DEFAULT '',shipping_cost REAL DEFAULT 0,free_shipping INTEGER DEFAULT 0,seo_title TEXT DEFAULT '',seo_description TEXT DEFAULT '',seo_keywords TEXT DEFAULT '',badge TEXT DEFAULT '',featured INTEGER DEFAULT 0,new_product INTEGER DEFAULT 0,bestseller INTEGER DEFAULT 0,active INTEGER DEFAULT 1,image TEXT DEFAULT '',gallery TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
 for k,v in {'site_name':'شیرآلات مدرن','tagline':'ویترین آنلاین محصولات آشپزخانه و سرویس بهداشتی','phone':'09120000000','address':'تهران','hero_title':'خانه‌ای زیباتر با انتخابی حرفه‌ای','hero_text':'شیرآلات، سینک، گاز، هود و تجهیزات آشپزخانه را در یک ویترین مدرن ببینید.'}.items(): c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,v))
 if c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n']==0:
  for n,s in [('شیرآلات','faucets'),('سینک','sinks'),('گاز','cookers'),('هود','hoods'),('تجهیزات آشپزخانه','kitchen')]: c.execute('INSERT INTO categories(name,slug) VALUES(?,?)',(n,s))
 c.commit(); c.close()

def migrate():
 c=db(); cols={r['name'] for r in c.execute('PRAGMA table_info(products)')}; additions={'model':'TEXT DEFAULT ""','sku':'TEXT DEFAULT ""','short_description':'TEXT DEFAULT ""','price':'REAL DEFAULT 0','sale_price':'REAL DEFAULT 0','stock':'INTEGER DEFAULT 0','color':'TEXT DEFAULT ""','colors':'TEXT DEFAULT ""','material':'TEXT DEFAULT ""','finish':'TEXT DEFAULT ""','length':'TEXT DEFAULT ""','width':'TEXT DEFAULT ""','height':'TEXT DEFAULT ""','weight':'TEXT DEFAULT ""','package_dimensions':'TEXT DEFAULT ""','package_weight':'TEXT DEFAULT ""','warranty':'TEXT DEFAULT ""','warranty_company':'TEXT DEFAULT ""','shipping_time':'TEXT DEFAULT ""','shipping_cost':'REAL DEFAULT 0','free_shipping':'INTEGER DEFAULT 0','seo_title':'TEXT DEFAULT ""','seo_description':'TEXT DEFAULT ""','seo_keywords':'TEXT DEFAULT ""','badge':'TEXT DEFAULT ""','new_product':'INTEGER DEFAULT 0','bestseller':'INTEGER DEFAULT 0','gallery':'TEXT DEFAULT ""'}
 for k,v in additions.items():
  if k not in cols: c.execute(f'ALTER TABLE products ADD COLUMN {k} {v}')
 c.commit(); c.close()
init_db(); migrate()
@app.context_processor
def ctx():
 c=db(); cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall(); c.close(); c2=db(); s={r['key']:r['value'] for r in c2.execute('SELECT * FROM settings')}; c2.close(); return {'settings':s,'nav_categories':cats}
def admin(f):
 @wraps(f)
 def w(*a,**k): return f(*a,**k) if session.get('admin') else redirect(url_for('login',next=request.path))
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
 if request.method=='POST' and request.form.get('username')==os.getenv('ADMIN_USERNAME','admin') and request.form.get('password')==os.getenv('ADMIN_PASSWORD','ChangeThisPassword_123!'): session['admin']=True; return redirect(request.args.get('next') or url_for('admin_home'))
 if request.method=='POST': flash('نام کاربری یا رمز عبور اشتباه است.','error')
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
  f=request.files.get('image'); img=''
  if f and f.filename: ext=f.filename.rsplit('.',1)[-1].lower(); fn=secure_filename(f.filename.rsplit('.',1)[0])+'_'+uuid.uuid4().hex[:8]+'.'+ext; f.save(UP/fn); img=fn
  name=request.form.get('name','').strip()
  if name:
   fields=['name','category_id','brand','model','sku','short_description','description','specs','price','sale_price','stock','color','colors','material','finish','length','width','height','weight','package_dimensions','package_weight','warranty','warranty_company','shipping_time','shipping_cost','seo_title','seo_description','seo_keywords','badge']; vals=[request.form.get(x,'') for x in fields]; vals[1]=request.form.get('category_id') or None
   flags=[1 if request.form.get(x) else 0 for x in ['free_shipping','featured','new_product','bestseller']]; c.execute('INSERT INTO products('+','.join(fields)+',free_shipping,featured,new_product,bestseller,image,gallery) VALUES('+','.join('?' for _ in fields)+',?,?,?,?,?,?)',vals+flags+[img,request.form.get('gallery','')]); c.commit(); flash('محصول کامل با موفقیت اضافه شد.','ok')
 rows=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC').fetchall(); c.close(); return render_template('manage_products.html',products=rows,categories=cats)
@app.route('/admin/products/edit/<int:pid>',methods=['GET','POST'])
@admin
def edit_product(pid):
 c=db(); cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall(); p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
 if not p: c.close(); abort(404)
 if request.method=='POST':
  fields=['name','category_id','brand','model','sku','short_description','description','specs','price','sale_price','stock','color','colors','material','finish','length','width','height','weight','package_dimensions','package_weight','warranty','warranty_company','shipping_time','shipping_cost','seo_title','seo_description','seo_keywords','badge','gallery']; vals=[request.form.get(x,'') for x in fields]; vals[1]=request.form.get('category_id') or None; flags=[1 if request.form.get(x) else 0 for x in ['free_shipping','featured','new_product','bestseller']]
  sets=','.join(f'{x}=?' for x in fields)+',free_shipping=?,featured=?,new_product=?,bestseller=?'; c.execute('UPDATE products SET '+sets+' WHERE id=?',vals+flags+[pid]); c.commit(); flash('محصول ویرایش شد.','ok'); return redirect(url_for('admin_products'))
 c.close(); return render_template('edit_product.html',product=p,categories=cats)
@app.post('/admin/products/delete/<int:pid>')
@admin
def delete_product(pid):
 c=db(); row=c.execute('SELECT image FROM products WHERE id=?',(pid,)).fetchone(); c.execute('DELETE FROM products WHERE id=?',(pid,)); c.commit(); c.close();
 if row and row['image']:
  try:(UP/row['image']).unlink(missing_ok=True)
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
  if f and f.filename: ext=f.filename.rsplit('.',1)[-1].lower();fn=secure_filename(f.filename.rsplit('.',1)[0])+'_'+uuid.uuid4().hex[:8]+'.'+ext;f.save(UP/fn);flash('تصویر آپلود شد.','ok')
 files=[{'name':p.name,'size':p.stat().st_size,'mtime':datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')} for p in sorted(UP.iterdir(),key=lambda x:x.stat().st_mtime,reverse=True) if p.is_file()] if UP.exists() else [];return render_template('admin_media.html',files=files)
@app.post('/admin/media/delete/<name>')
@admin
def delete_media(name):
 p=(UP/name).resolve()
 if p.parent==UP.resolve() and p.is_file():p.unlink()
 return redirect(url_for('admin_media'))
@app.route('/admin/system')
@admin
def admin_system():
 c=db();data={'products':c.execute('SELECT COUNT(*) n FROM products').fetchone()['n'],'categories':c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n'],'settings':c.execute('SELECT COUNT(*) n FROM settings').fetchone()['n']};c.close();data.update({'database_size':DB.stat().st_size if DB.exists() else 0,'uploads_count':len([p for p in UP.iterdir() if p.is_file()]),'uploads_size':sum(p.stat().st_size for p in UP.iterdir() if p.is_file())});return render_template('admin_system.html',data=data)
@app.route('/admin/backup')
@admin
def admin_backup():
 backup=BASE/'instance'/f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db';shutil.copy2(DB,backup);return send_file(backup,as_attachment=True,download_name=backup.name)
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)))