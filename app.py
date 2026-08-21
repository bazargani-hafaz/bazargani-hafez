import os, sqlite3, uuid
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.utils import secure_filename
BASE=Path(__file__).resolve().parent; DB=BASE/'instance/store.db'; UP=BASE/'static/uploads'; UP.mkdir(parents=True,exist_ok=True); DB.parent.mkdir(parents=True,exist_ok=True)
app=Flask(__name__); app.secret_key=os.getenv('SECRET_KEY','change-me'); app.config['MAX_CONTENT_LENGTH']=8*1024*1024
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
 c=db(); c.executescript("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL); CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL,category_id INTEGER,brand TEXT DEFAULT '',description TEXT DEFAULT '',specs TEXT DEFAULT '',featured INTEGER DEFAULT 0,active INTEGER DEFAULT 1,image TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
 for k,v in {'site_name':'شیرآلات مدرن','tagline':'ویترین آنلاین محصولات آشپزخانه و سرویس بهداشتی','phone':'09120000000','address':'تهران','hero_title':'خانه‌ای زیباتر با انتخابی حرفه‌ای','hero_text':'شیرآلات، سینک، گاز، هود و تجهیزات آشپزخانه را در یک ویترین مدرن ببینید.'}.items(): c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,v))
 if c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n']==0:
  for n,s in [('شیرآلات','faucets'),('سینک','sinks'),('گاز','cookers'),('هود','hoods'),('تجهیزات آشپزخانه','kitchen')]: c.execute('INSERT INTO categories(name,slug) VALUES(?,?)',(n,s))
 c.commit(); c.close()
def settings():
 c=db(); x={r['key']:r['value'] for r in c.execute('SELECT * FROM settings')}; c.close(); return x
init_db()
@app.context_processor
def ctx():
 c=db(); cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall(); c.close(); return {'settings':settings(),'nav_categories':cats}
def admin(f):
 @wraps(f)
 def w(*a,**k):
  return f(*a,**k) if session.get('admin') else redirect(url_for('login',next=request.path))
 return w
@app.route('/')
def home():
 c=db(); p=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 ORDER BY p.featured DESC,p.id DESC LIMIT 8').fetchall(); cats=c.execute('SELECT c.*,COUNT(p.id) count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id').fetchall(); c.close(); return render_template('index.html',products=p,categories=cats)
@app.route('/products')
def products():
 q=request.args.get('q','').strip(); cat=request.args.get('cat',''); c=db(); sql='SELECT p.*,c.name category,c.slug catslug FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1'; a=[]
 if q: sql+=' AND (p.name LIKE ? OR p.brand LIKE ? OR p.description LIKE ?)'; a += [f'%{q}%']*3
 if cat: sql+=' AND c.slug=?'; a.append(cat)
 rows=c.execute(sql+' ORDER BY p.featured DESC,p.id DESC',a).fetchall(); c.close(); return render_template('products.html',products=rows,q=q,selected=cat)
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
@app.route('/admin/settings',methods=['GET','POST'])
@admin
def admin_settings():
 if request.method=='POST':
  c=db();
  for k in ['site_name','tagline','phone','address','hero_title','hero_text']: c.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,request.form.get(k,'')))
  c.commit(); c.close(); flash('تنظیمات ذخیره شد.','ok')
 return render_template('settings.html')
@app.route('/admin/products',methods=['GET','POST'])
@admin
def admin_products():
 c=db(); cats=c.execute('SELECT * FROM categories').fetchall()
 if request.method=='POST':
  name=request.form.get('name','').strip(); f=request.files.get('image'); img=''
  if f and f.filename and f.filename.rsplit('.',1)[-1].lower() in {'png','jpg','jpeg','webp','gif'}:
   ext=f.filename.rsplit('.',1)[-1].lower(); fn=secure_filename(f.filename.rsplit('.',1)[0])+'_'+uuid.uuid4().hex[:8]+'.'+ext; f.save(UP/fn); img=fn
  if name: c.execute('INSERT INTO products(name,slug,category_id,brand,description,specs,featured,image) VALUES(?,?,?,?,?,?,?,?)',(name,uuid.uuid4().hex[:12],request.form.get('category_id') or None,request.form.get('brand',''),request.form.get('description',''),request.form.get('specs',''),1 if request.form.get('featured') else 0,img)); c.commit(); flash('محصول اضافه شد.','ok')
 rows=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC').fetchall(); c.close(); return render_template('manage_products.html',products=rows,categories=cats)
@app.post('/admin/products/delete/<int:pid>')
@admin
def delete_product(pid):
 c=db(); c.execute('DELETE FROM products WHERE id=?',(pid,)); c.commit(); c.close(); return redirect(url_for('admin_products'))
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',5000)))
