"""
============================================================
 Smart Pharmacy Management System  -  Flask main application
============================================================
DBMS Lab Project (4th Semester)

Modules:
  1. Inventory & Supplier Management
  2. Sales & Billing (POS)
  3. Customer & Prescription Management
  4. Alerts, Reports & Admin Dashboard

Run with:  python app.py   then open http://127.0.0.1:5000
"""

from functools import wraps
from datetime import date

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash)
from werkzeug.security import generate_password_hash, check_password_hash

import db
from config import SECRET_KEY, DEFAULT_TAX_PERCENT

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ============================================================
#  Helpers: login + role protection
# ============================================================
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    """Restrict a page to certain roles (Admin always allowed)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles and session.get("role") != "Admin":
                flash("You do not have permission to view that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def seed_password_hashes():
    """
    On first run, replace the plain-text demo passwords from schema.sql
    with proper hashes so login works securely.
    """
    try:
        users = db.query("SELECT user_id, password FROM users")
        for u in users:
            if not u["password"].startswith("pbkdf2:") and not u["password"].startswith("scrypt:"):
                db.execute(
                    "UPDATE users SET password=%s WHERE user_id=%s",
                    (generate_password_hash(u["password"]), u["user_id"]),
                )
    except Exception as e:
        print("Could not seed password hashes (is MySQL running?):", e)


# ============================================================
#  Authentication
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = db.query(
            "SELECT * FROM users WHERE username=%s", (username,), fetchone=True
        )
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            db.log_activity(user["user_id"], "Logged in")
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user_id" in session:
        db.log_activity(session["user_id"], "Logged out")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ============================================================
#  Dashboard  (Module 4)
# ============================================================
@app.route("/")
@login_required
def dashboard():
    stats = {
        "medicines": db.query("SELECT COUNT(*) c FROM medicines", fetchone=True)["c"],
        "customers": db.query("SELECT COUNT(*) c FROM customers", fetchone=True)["c"],
        "suppliers": db.query("SELECT COUNT(*) c FROM suppliers", fetchone=True)["c"],
        "sales_today": db.query(
            "SELECT COUNT(*) c FROM sales WHERE DATE(sale_date)=CURRENT_DATE",
            fetchone=True)["c"],
        "revenue_today": db.query(
            "SELECT COALESCE(SUM(total),0) t FROM sales WHERE DATE(sale_date)=CURRENT_DATE",
            fetchone=True)["t"],
    }
    low_stock = db.query("SELECT * FROM v_low_stock ORDER BY total_stock ASC")
    expiring = db.query("SELECT * FROM v_expiring_soon LIMIT 6")
    top_meds = db.query("""
        SELECT m.name, SUM(si.quantity) AS qty
        FROM sale_items si JOIN medicines m ON m.medicine_id=si.medicine_id
        GROUP BY m.medicine_id, m.name
        ORDER BY qty DESC LIMIT 5
    """)
    return render_template("dashboard.html", stats=stats, low_stock=low_stock,
                           expiring=expiring, top_meds=top_meds)


# ============================================================
#  MODULE 1 — Inventory & Supplier Management
# ============================================================

# ---------- Medicines ----------
@app.route("/medicines")
@login_required
def medicines():
    search = request.args.get("q", "").strip()
    sql = """
        SELECT m.*, c.name AS category_name,
               COALESCE((SELECT SUM(b.quantity) FROM batches b
                         WHERE b.medicine_id=m.medicine_id),0) AS stock
        FROM medicines m
        LEFT JOIN categories c ON c.category_id=m.category_id
    """
    params = ()
    if search:
        sql += " WHERE m.name LIKE %s OR m.barcode LIKE %s"
        params = (f"%{search}%", f"%{search}%")
    sql += " ORDER BY m.name"
    meds = db.query(sql, params)
    categories = db.query("SELECT * FROM categories ORDER BY name")
    return render_template("medicines.html", medicines=meds,
                           categories=categories, search=search)


@app.route("/medicines/add", methods=["POST"])
@login_required
def add_medicine():
    f = request.form
    db.execute("""
        INSERT INTO medicines
          (name, category_id, dosage, unit_price, barcode,
           requires_prescription, reorder_level)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (f["name"], f["category_id"] or None, f["dosage"], f["unit_price"],
          f["barcode"] or None, 1 if f.get("requires_prescription") else 0,
          f["reorder_level"] or 20))
    db.log_activity(session["user_id"], f"Added medicine: {f['name']}")
    flash("Medicine added.", "success")
    return redirect(url_for("medicines"))


@app.route("/medicines/edit/<int:mid>", methods=["POST"])
@login_required
def edit_medicine(mid):
    f = request.form
    db.execute("""
        UPDATE medicines SET name=%s, category_id=%s, dosage=%s,
               unit_price=%s, barcode=%s, requires_prescription=%s,
               reorder_level=%s
        WHERE medicine_id=%s
    """, (f["name"], f["category_id"] or None, f["dosage"], f["unit_price"],
          f["barcode"] or None, 1 if f.get("requires_prescription") else 0,
          f["reorder_level"] or 20, mid))
    db.log_activity(session["user_id"], f"Updated medicine #{mid}")
    flash("Medicine updated.", "success")
    return redirect(url_for("medicines"))


@app.route("/medicines/delete/<int:mid>")
@role_required("Admin", "Pharmacist")
def delete_medicine(mid):
    db.execute("DELETE FROM medicines WHERE medicine_id=%s", (mid,))
    db.log_activity(session["user_id"], f"Deleted medicine #{mid}")
    flash("Medicine deleted.", "info")
    return redirect(url_for("medicines"))


# ---------- Suppliers ----------
@app.route("/suppliers")
@login_required
def suppliers():
    sup = db.query("SELECT * FROM suppliers ORDER BY name")
    return render_template("suppliers.html", suppliers=sup)


@app.route("/suppliers/add", methods=["POST"])
@login_required
def add_supplier():
    f = request.form
    db.execute("""INSERT INTO suppliers
                  (name, contact_person, phone, email, address)
                  VALUES (%s,%s,%s,%s,%s)""",
               (f["name"], f["contact_person"], f["phone"], f["email"], f["address"]))
    flash("Supplier added.", "success")
    return redirect(url_for("suppliers"))


@app.route("/suppliers/edit/<int:sid>", methods=["POST"])
@login_required
def edit_supplier(sid):
    f = request.form
    db.execute("""UPDATE suppliers SET name=%s, contact_person=%s,
                  phone=%s, email=%s, address=%s WHERE supplier_id=%s""",
               (f["name"], f["contact_person"], f["phone"], f["email"],
                f["address"], sid))
    flash("Supplier updated.", "success")
    return redirect(url_for("suppliers"))


@app.route("/suppliers/delete/<int:sid>")
@role_required("Admin", "Pharmacist")
def delete_supplier(sid):
    db.execute("DELETE FROM suppliers WHERE supplier_id=%s", (sid,))
    flash("Supplier deleted.", "info")
    return redirect(url_for("suppliers"))


# ---------- Batches / Stock-in ----------
@app.route("/batches")
@login_required
def batches():
    rows = db.query("""
        SELECT b.*, m.name AS medicine_name, s.name AS supplier_name,
               DATEDIFF(b.expiry_date, CURRENT_DATE) AS days_left
        FROM batches b
        JOIN medicines m ON m.medicine_id=b.medicine_id
        LEFT JOIN suppliers s ON s.supplier_id=b.supplier_id
        ORDER BY b.expiry_date ASC
    """)
    meds = db.query("SELECT medicine_id, name FROM medicines ORDER BY name")
    sup = db.query("SELECT supplier_id, name FROM suppliers ORDER BY name")
    return render_template("batches.html", batches=rows, medicines=meds, suppliers=sup)


@app.route("/batches/add", methods=["POST"])
@login_required
def add_batch():
    f = request.form
    db.execute("""INSERT INTO batches
                  (medicine_id, supplier_id, batch_number, mfg_date,
                   expiry_date, quantity)
                  VALUES (%s,%s,%s,%s,%s,%s)""",
               (f["medicine_id"], f["supplier_id"] or None, f["batch_number"],
                f["mfg_date"] or None, f["expiry_date"], f["quantity"]))
    db.log_activity(session["user_id"], "Stock-in: new batch added")
    flash("Stock added (batch created). The expiry trigger has run automatically.", "success")
    return redirect(url_for("batches"))


@app.route("/batches/delete/<int:bid>")
@role_required("Admin", "Pharmacist")
def delete_batch(bid):
    db.execute("DELETE FROM batches WHERE batch_id=%s", (bid,))
    flash("Batch deleted.", "info")
    return redirect(url_for("batches"))


# ============================================================
#  MODULE 2 — Sales & Billing (POS)
# ============================================================
@app.route("/pos")
@login_required
def pos():
    search = request.args.get("q", "").strip()
    meds = []
    if search:
        meds = db.query("""
            SELECT m.medicine_id, m.name, m.unit_price, m.requires_prescription,
                   COALESCE(SUM(b.quantity),0) AS stock
            FROM medicines m
            LEFT JOIN batches b ON b.medicine_id=m.medicine_id
            WHERE m.name LIKE %s OR m.barcode LIKE %s
            GROUP BY m.medicine_id, m.name, m.unit_price, m.requires_prescription
            ORDER BY m.name
        """, (f"%{search}%", f"%{search}%"))
    cart = session.get("cart", [])
    customers = db.query("SELECT customer_id, name FROM customers ORDER BY name")
    subtotal = sum(item["line_total"] for item in cart)
    return render_template("pos.html", medicines=meds, search=search, cart=cart,
                           customers=customers, subtotal=subtotal,
                           tax_pct=DEFAULT_TAX_PERCENT)


@app.route("/pos/add/<int:mid>")
@login_required
def pos_add(mid):
    med = db.query("""
        SELECT m.medicine_id, m.name, m.unit_price,
               COALESCE(SUM(b.quantity),0) AS stock
        FROM medicines m LEFT JOIN batches b ON b.medicine_id=m.medicine_id
        WHERE m.medicine_id=%s GROUP BY m.medicine_id, m.name, m.unit_price
    """, (mid,), fetchone=True)
    if not med or med["stock"] <= 0:
        flash("That medicine is out of stock.", "warning")
        return redirect(url_for("pos"))

    cart = session.get("cart", [])
    for item in cart:
        if item["medicine_id"] == mid:
            item["quantity"] += 1
            item["line_total"] = round(item["quantity"] * item["unit_price"], 2)
            break
    else:
        cart.append({
            "medicine_id": mid,
            "name": med["name"],
            "unit_price": float(med["unit_price"]),
            "quantity": 1,
            "line_total": float(med["unit_price"]),
        })
    session["cart"] = cart
    return redirect(url_for("pos"))


@app.route("/pos/remove/<int:mid>")
@login_required
def pos_remove(mid):
    session["cart"] = [i for i in session.get("cart", []) if i["medicine_id"] != mid]
    return redirect(url_for("pos"))


@app.route("/pos/clear")
@login_required
def pos_clear():
    session.pop("cart", None)
    return redirect(url_for("pos"))


@app.route("/pos/checkout", methods=["POST"])
@login_required
def pos_checkout():
    """
    Complete the sale as a TRANSACTION:
      - create the bill (stored procedure)
      - insert each line item (trigger auto-deducts stock, FIFO by expiry)
      - finalize totals (stored procedure)
    If anything fails, everything is rolled back.
    """
    cart = session.get("cart", [])
    if not cart:
        flash("Cart is empty.", "warning")
        return redirect(url_for("pos"))

    customer_id = request.form.get("customer_id") or 0
    discount_pct = float(request.form.get("discount_pct") or 0)
    tax_pct = float(request.form.get("tax_pct") or DEFAULT_TAX_PERCENT)

    conn = db.get_connection()
    try:
        conn.start_transaction()
        cur = conn.cursor()

        # 1) create the sale via stored procedure -> OUT sale_id.
        # callproc returns the argument tuple with OUT values filled in,
        # so the 4th item (index 3) is the new sale_id.
        result = cur.callproc("sp_create_sale",
                              (int(customer_id), session["user_id"], 0, 0))
        sale_id = result[3]

        # 2) add each line item, picking batches FIFO (soonest expiry first)
        for item in cart:
            remaining = item["quantity"]
            cur.execute("""
                SELECT batch_id, quantity FROM batches
                WHERE medicine_id=%s AND quantity>0 AND expiry_date>=CURRENT_DATE
                ORDER BY expiry_date ASC
            """, (item["medicine_id"],))
            batches_avail = cur.fetchall()

            total_avail = sum(b[1] for b in batches_avail)
            if total_avail < remaining:
                raise Exception(f"Not enough stock for {item['name']}.")

            for batch_id, qty in batches_avail:
                if remaining <= 0:
                    break
                take = min(qty, remaining)
                line_total = round(take * item["unit_price"], 2)
                # trigger trg_deduct_stock fires here and updates the batch
                cur.execute("""
                    INSERT INTO sale_items
                      (sale_id, medicine_id, batch_id, quantity, unit_price, line_total)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (sale_id, item["medicine_id"], batch_id, take,
                      item["unit_price"], line_total))
                remaining -= take

        # 3) finalize totals via stored procedure
        cur.callproc("sp_finalize_sale", (sale_id, discount_pct, tax_pct))

        conn.commit()
        cur.close()
        conn.close()

        db.log_activity(session["user_id"], f"Completed sale #{sale_id}")
        session.pop("cart", None)
        flash(f"Sale completed! Invoice #{sale_id} generated.", "success")
        return redirect(url_for("invoice", sale_id=sale_id))

    except Exception as e:
        conn.rollback()
        conn.close()
        flash(f"Checkout failed and was rolled back: {e}", "danger")
        return redirect(url_for("pos"))


@app.route("/invoice/<int:sale_id>")
@login_required
def invoice(sale_id):
    sale = db.query("""
        SELECT s.*, c.name AS customer_name, u.full_name AS cashier
        FROM sales s
        LEFT JOIN customers c ON c.customer_id=s.customer_id
        LEFT JOIN users u ON u.user_id=s.user_id
        WHERE s.sale_id=%s
    """, (sale_id,), fetchone=True)
    items = db.query("""
        SELECT si.*, m.name AS medicine_name, b.batch_number
        FROM sale_items si
        JOIN medicines m ON m.medicine_id=si.medicine_id
        JOIN batches b ON b.batch_id=si.batch_id
        WHERE si.sale_id=%s
    """, (sale_id,))
    if not sale:
        flash("Invoice not found.", "danger")
        return redirect(url_for("sales"))
    return render_template("invoice.html", sale=sale, items=items)


@app.route("/sales")
@login_required
def sales():
    rows = db.query("""
        SELECT s.*, c.name AS customer_name, u.full_name AS cashier
        FROM sales s
        LEFT JOIN customers c ON c.customer_id=s.customer_id
        LEFT JOIN users u ON u.user_id=s.user_id
        ORDER BY s.sale_date DESC
    """)
    return render_template("sales.html", sales=rows)


# ============================================================
#  MODULE 3 — Customers, Doctors & Prescriptions
# ============================================================
@app.route("/customers")
@login_required
def customers():
    rows = db.query("SELECT * FROM customers ORDER BY name")
    return render_template("customers.html", customers=rows)


@app.route("/customers/add", methods=["POST"])
@login_required
def add_customer():
    f = request.form
    db.execute("""INSERT INTO customers (name, phone, email, address, medical_notes)
                  VALUES (%s,%s,%s,%s,%s)""",
               (f["name"], f["phone"], f["email"], f["address"], f["medical_notes"]))
    flash("Customer added.", "success")
    return redirect(url_for("customers"))


@app.route("/customers/edit/<int:cid>", methods=["POST"])
@login_required
def edit_customer(cid):
    f = request.form
    db.execute("""UPDATE customers SET name=%s, phone=%s, email=%s,
                  address=%s, medical_notes=%s WHERE customer_id=%s""",
               (f["name"], f["phone"], f["email"], f["address"],
                f["medical_notes"], cid))
    flash("Customer updated.", "success")
    return redirect(url_for("customers"))


@app.route("/customers/delete/<int:cid>")
@role_required("Admin", "Pharmacist")
def delete_customer(cid):
    db.execute("DELETE FROM customers WHERE customer_id=%s", (cid,))
    flash("Customer deleted.", "info")
    return redirect(url_for("customers"))


@app.route("/doctors")
@login_required
def doctors():
    rows = db.query("SELECT * FROM doctors ORDER BY name")
    return render_template("doctors.html", doctors=rows)


@app.route("/doctors/add", methods=["POST"])
@login_required
def add_doctor():
    f = request.form
    db.execute("""INSERT INTO doctors (name, specialization, phone, hospital)
                  VALUES (%s,%s,%s,%s)""",
               (f["name"], f["specialization"], f["phone"], f["hospital"]))
    flash("Doctor added.", "success")
    return redirect(url_for("doctors"))


@app.route("/doctors/delete/<int:did>")
@role_required("Admin", "Pharmacist")
def delete_doctor(did):
    db.execute("DELETE FROM doctors WHERE doctor_id=%s", (did,))
    flash("Doctor deleted.", "info")
    return redirect(url_for("doctors"))


@app.route("/prescriptions")
@login_required
def prescriptions():
    rows = db.query("""
        SELECT p.*, c.name AS customer_name, d.name AS doctor_name
        FROM prescriptions p
        JOIN customers c ON c.customer_id=p.customer_id
        LEFT JOIN doctors d ON d.doctor_id=p.doctor_id
        ORDER BY p.prescription_date DESC
    """)
    customers = db.query("SELECT customer_id, name FROM customers ORDER BY name")
    doctors_list = db.query("SELECT doctor_id, name FROM doctors ORDER BY name")
    # refill reminders: chronic prescriptions due within 7 days
    reminders = db.query("""
        SELECT p.prescription_id, c.name AS customer_name, p.next_refill_date,
               DATEDIFF(p.next_refill_date, CURRENT_DATE) AS days_left
        FROM prescriptions p JOIN customers c ON c.customer_id=p.customer_id
        WHERE p.is_chronic=1 AND p.next_refill_date IS NOT NULL
          AND p.next_refill_date <= DATE_ADD(CURRENT_DATE, INTERVAL 7 DAY)
        ORDER BY p.next_refill_date ASC
    """)
    return render_template("prescriptions.html", prescriptions=rows,
                           customers=customers, doctors=doctors_list,
                           reminders=reminders)


@app.route("/prescriptions/add", methods=["POST"])
@login_required
def add_prescription():
    f = request.form
    db.execute("""INSERT INTO prescriptions
                  (customer_id, doctor_id, prescription_date, notes,
                   is_chronic, next_refill_date)
                  VALUES (%s,%s,%s,%s,%s,%s)""",
               (f["customer_id"], f["doctor_id"] or None, f["prescription_date"],
                f["notes"], 1 if f.get("is_chronic") else 0,
                f["next_refill_date"] or None))
    flash("Prescription saved.", "success")
    return redirect(url_for("prescriptions"))


@app.route("/prescriptions/delete/<int:pid>")
@login_required
def delete_prescription(pid):
    db.execute("DELETE FROM prescriptions WHERE prescription_id=%s", (pid,))
    flash("Prescription deleted.", "info")
    return redirect(url_for("prescriptions"))


# ============================================================
#  MODULE 4 — Alerts, Reports & Admin
# ============================================================
@app.route("/alerts")
@login_required
def alerts():
    days = int(request.args.get("days", 90))
    # use the stored procedure for the expiry list
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    cur.callproc("sp_expiry_check", (days,))
    expiring = []
    for result in cur.stored_results():
        expiring = result.fetchall()
    cur.close()
    conn.close()

    low_stock = db.query("SELECT * FROM v_low_stock ORDER BY total_stock ASC")
    return render_template("alerts.html", expiring=expiring,
                           low_stock=low_stock, days=days)


@app.route("/reports")
@login_required
def reports():
    daily = db.query("""
        SELECT DATE(sale_date) AS d, COUNT(*) AS bills, SUM(total) AS revenue
        FROM sales GROUP BY DATE(sale_date) ORDER BY d DESC LIMIT 14
    """)
    monthly = db.query("""
        SELECT DATE_FORMAT(sale_date,'%Y-%m') AS m, COUNT(*) AS bills,
               SUM(total) AS revenue
        FROM sales GROUP BY m ORDER BY m DESC LIMIT 12
    """)
    top_meds = db.query("""
        SELECT m.name, SUM(si.quantity) AS qty, SUM(si.line_total) AS revenue
        FROM sale_items si JOIN medicines m ON m.medicine_id=si.medicine_id
        GROUP BY m.medicine_id, m.name ORDER BY qty DESC LIMIT 10
    """)
    totals = db.query("""
        SELECT COUNT(*) AS bills, COALESCE(SUM(total),0) AS revenue FROM sales
    """, fetchone=True)
    return render_template("reports.html", daily=daily, monthly=monthly,
                           top_meds=top_meds, totals=totals)


@app.route("/users")
@role_required("Admin")
def users():
    rows = db.query("SELECT user_id, username, full_name, role, created_at FROM users ORDER BY user_id")
    logs = db.query("""
        SELECT a.*, u.username FROM activity_log a
        LEFT JOIN users u ON u.user_id=a.user_id
        ORDER BY a.created_at DESC LIMIT 30
    """)
    return render_template("users.html", users=rows, logs=logs)


@app.route("/users/add", methods=["POST"])
@role_required("Admin")
def add_user():
    f = request.form
    existing = db.query("SELECT user_id FROM users WHERE username=%s",
                        (f["username"],), fetchone=True)
    if existing:
        flash("Username already exists.", "warning")
        return redirect(url_for("users"))
    db.execute("""INSERT INTO users (username, password, full_name, role)
                  VALUES (%s,%s,%s,%s)""",
               (f["username"], generate_password_hash(f["password"]),
                f["full_name"], f["role"]))
    db.log_activity(session["user_id"], f"Created user {f['username']}")
    flash("User created.", "success")
    return redirect(url_for("users"))


@app.route("/users/delete/<int:uid>")
@role_required("Admin")
def delete_user(uid):
    if uid == session["user_id"]:
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("users"))
    db.execute("DELETE FROM users WHERE user_id=%s", (uid,))
    flash("User deleted.", "info")
    return redirect(url_for("users"))


# ------------------------------------------------------------
#  Make "today" available to every template (for date inputs)
# ------------------------------------------------------------
@app.context_processor
def inject_today():
    return {"today": date.today().isoformat()}


if __name__ == "__main__":
    seed_password_hashes()
    app.run(debug=True)
