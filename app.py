import os, sqlite3, uuid, shutil, json, re, time
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, make_response
from werkzeug.utils import secure_filename

BASE=Path(__file__).resolve().parent
# Railway Persistent Volume is mounted at /data. Keep all mutable application data there.
DATA_ROOT=Path(os.getenv('DATA_ROOT','/data'))
if not DATA_ROOT.exists():
    DATA_ROOT=BASE/'instance'
DATA_ROOT.mkdir(parents=True,exist_ok=True)
DB=DATA_ROOT/'store.db'
UP=DATA_ROOT/'uploads'
UP.mkdir(parents=True,exist_ok=True)

# One-time, non-destructive migration from the old ephemeral locations.
# Existing /data data always wins; nothing on the volume is overwritten.
OLD_DB=BASE/'instance/store.db'
OLD_UP=BASE/'static/uploads'
if DB != OLD_DB and not DB.exists() and OLD_DB.exists():
    shutil.copy2(OLD_DB,DB)
if UP != OLD_UP and OLD_UP.exists():
    for src in OLD_UP.iterdir():
        dst=UP/src.name
        if src.is_file() and not dst.exists():
            shutil.copy2(src,dst)

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


# ... existing application routes and remaining code continue unchanged ...
