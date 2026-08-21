
import os, sqlite3, secrets, hashlib
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort

BASE = Path(__file__).resolve().parent
DB = BASE / "store.db"
UPLOADS = BASE / "static" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin123")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "8"))
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED = {"jpg","jpeg","png","webp","gif"}

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        slug TEXT NOT NULL UNIQUE,
        sort_order INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        category_id INTEGER,
        brand TEXT DEFAULT '',
        price TEXT DEFAULT '',
        discount TEXT DEFAULT '',
        color TEXT DEFAULT '',
        material TEXT DEFAULT '',
        dimensions TEXT DEFAULT '',
        description TEXT DEFAULT '',
        stock TEXT DEFAULT '',
        code TEXT DEFAULT '',
        image TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
    );
    """)
    defaults = {
        "store_name": "خانه شیرآلات",
        "store_tagline": "نمایش محصولات شیرآلات و لوازم آشپزخانه",
        "phone": "",
        "address": "",
        "telegram": "",
        "whatsapp": "",
        "logo": ""
    }
    for k,v in defaults.items():
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
    if con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        for i,n in enumerate(["شیرآلات","سینک","اجاق گاز","هود","فر","لوازم آشپزخانه","سایر"]):
            slug = slugify(n)
            con.execute("INSERT INTO categories(name,slug,sort_order) VALUES(?,?,?)",(n,slug,i))
    con.commit(); con.close()

def slugify(s):
    s = (s or "").strip().lower()
    repl = {" ":"-","/":"-","_":"-"}
    for a,b in repl.items(): s=s.replace(a,b)
    return "".join(c for c in s if c.isalnum() or c in "-_").strip("-") or secrets.token_hex(4)

def unique_slug(name, current_id=None):
    base = slugify(name)
    slug = base
    i = 2
    con = db()
    while True:
        row = con.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
        if not row or (current_id and row["id"] == current_id):
            con.close(); return slug
        slug=f"{base}-{i}"; i+=1

def settings():
    con=db()
    data={r["key"]:r["value"] for r in con.execute("SELECT key,value FROM settings")}
    con.close(); return data

def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper

def valid_file(f):
    return f and f.filename and "." in f.filename and f.filename.rsplit(".",1)[1].lower() in ALLOWED

@app.context_processor
def inject():
    con=db()
    cats=con.execute("SELECT * FROM categories ORDER BY sort_order,name").fetchall()
    con.close()
    return {"site":settings(),"nav_categories":cats}

@app.route("/")
def home():
    con=db()
    products=con.execute("SELECT p.*,c.name category_name FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC").fetchall()
    con.close()
    return render_template("index.html", products=products)

@app.route("/category/<slug>")
def category(slug):
    con=db()
    cat=con.execute("SELECT * FROM categories WHERE slug=?", (slug,)).fetchone()
    if not cat: abort(404)
    products=con.execute("SELECT p.*,c.name category_name FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.category_id=? ORDER BY p.id DESC",(cat["id"],)).fetchall()
    con.close()
    return render_template("category.html", category=cat, products=products)

@app.route("/product/<slug>")
def product(slug):
    con=db()
    p=con.execute("SELECT p.*,c.name category_name FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.slug=?",(slug,)).fetchone()
    con.close()
    if not p: abort(404)
    return render_template("product.html", p=p)

@app.route("/admin/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form.get("username",""); pw=request.form.get("password","")
        if secrets.compare_digest(u,ADMIN_USER) and secrets.compare_digest(pw,ADMIN_PASS):
            session["admin"]=True
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("نام کاربری یا رمز عبور اشتباه است.","error")
    return render_template("login.html")

@app.route("/admin/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def dashboard():
    con=db()
    pc=con.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
    cc=con.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"]
    products=con.execute("SELECT p.*,c.name category_name FROM products p LEFT JOIN categories c ON c.id=p.category_id ORDER BY p.id DESC").fetchall()
    con.close()
    return render_template("admin.html", products=products, product_count=pc, category_count=cc)

@app.route("/admin/product/new", methods=["GET","POST"])
@admin_required
def new_product():
    con=db(); cats=con.execute("SELECT * FROM categories ORDER BY sort_order,name").fetchall()
    if request.method=="POST":
        f=request.files.get("image"); image=""
        if valid_file(f):
            ext=f.filename.rsplit(".",1)[1].lower()
            image=secrets.token_hex(12)+"."+ext; f.save(UPLOADS/image)
        name=request.form.get("name","").strip()
        if not name:
            flash("نام محصول الزامی است.","error"); con.close(); return render_template("product_form.html",p=None,cats=cats)
        con.execute("""INSERT INTO products(name,slug,category_id,brand,price,discount,color,material,dimensions,description,stock,code,image)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name,unique_slug(name),request.form.get("category_id") or None,request.form.get("brand",""),request.form.get("price",""),
                     request.form.get("discount",""),request.form.get("color",""),request.form.get("material",""),request.form.get("dimensions",""),
                     request.form.get("description",""),request.form.get("stock",""),request.form.get("code",""),image))
        con.commit(); con.close(); flash("محصول با موفقیت اضافه شد.","ok"); return redirect(url_for("dashboard"))
    con.close(); return render_template("product_form.html",p=None,cats=cats)

@app.route("/admin/product/<int:pid>/edit", methods=["GET","POST"])
@admin_required
def edit_product(pid):
    con=db(); p=con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    cats=con.execute("SELECT * FROM categories ORDER BY sort_order,name").fetchall()
    if not p: con.close(); abort(404)
    if request.method=="POST":
        image=p["image"]; f=request.files.get("image")
        if valid_file(f):
            if image:
                old=UPLOADS/image
                if old.exists(): old.unlink()
            ext=f.filename.rsplit(".",1)[1].lower(); image=secrets.token_hex(12)+"."+ext; f.save(UPLOADS/image)
        name=request.form.get("name","").strip()
        con.execute("""UPDATE products SET name=?,slug=?,category_id=?,brand=?,price=?,discount=?,color=?,material=?,dimensions=?,description=?,stock=?,code=?,image=? WHERE id=?""",
                    (name,unique_slug(name,pid),request.form.get("category_id") or None,request.form.get("brand",""),request.form.get("price",""),
                     request.form.get("discount",""),request.form.get("color",""),request.form.get("material",""),request.form.get("dimensions",""),
                     request.form.get("description",""),request.form.get("stock",""),request.form.get("code",""),image,pid))
        con.commit(); con.close(); flash("محصول ویرایش شد.","ok"); return redirect(url_for("dashboard"))
    con.close(); return render_template("product_form.html",p=p,cats=cats)

@app.post("/admin/product/<int:pid>/delete")
@admin_required
def delete_product(pid):
    con=db(); p=con.execute("SELECT image FROM products WHERE id=?",(pid,)).fetchone()
    if p:
        con.execute("DELETE FROM products WHERE id=?",(pid,)); con.commit()
        if p["image"] and (UPLOADS/p["image"]).exists(): (UPLOADS/p["image"]).unlink()
    con.close(); flash("محصول حذف شد.","ok"); return redirect(url_for("dashboard"))

@app.route("/admin/categories", methods=["GET","POST"])
@admin_required
def categories():
    con=db()
    if request.method=="POST":
        name=request.form.get("name","").strip()
        if name:
            try: con.execute("INSERT INTO categories(name,slug,sort_order) VALUES(?,?,?)",(name,slugify(name),request.form.get("sort_order") or 0)); con.commit()
            except sqlite3.IntegrityError: flash("این دسته‌بندی قبلاً وجود دارد.","error")
            else: flash("دسته‌بندی اضافه شد.","ok")
    cats=con.execute("SELECT c.*,COUNT(p.id) count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id ORDER BY c.sort_order,c.name").fetchall()
    con.close(); return render_template("categories.html",cats=cats)

@app.post("/admin/categories/<int:cid>/delete")
@admin_required
def delete_category(cid):
    con=db(); con.execute("DELETE FROM categories WHERE id=?",(cid,)); con.commit(); con.close()
    flash("دسته‌بندی حذف شد.","ok"); return redirect(url_for("categories"))

@app.route("/admin/settings", methods=["GET","POST"])
@admin_required
def admin_settings():
    if request.method=="POST":
        con=db()
        for key in ["store_name","store_tagline","phone","address","telegram","whatsapp"]:
            con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(key,request.form.get(key,"").strip()))
        con.commit(); con.close(); flash("تنظیمات ذخیره شد.","ok"); return redirect(url_for("admin_settings"))
    return render_template("settings.html")

@app.errorhandler(413)
def too_large(e): return "حجم فایل بیش از حد مجاز است.",413

init_db()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), debug=False)
