# 💊 Smart Pharmacy Management System

A database-driven web application that digitizes a retail pharmacy — inventory,
suppliers, POS billing, prescriptions, expiry/low-stock alerts and reports.

**DBMS Lab Project (4th Semester)** · Flask + MySQL + Bootstrap

---

## ✨ Features (4 Modules)

| Module | What it does |
|--------|--------------|
| **1. Inventory & Suppliers** | Add/edit/delete medicines, manage batches (with expiry), suppliers, stock-in |
| **2. Sales & Billing (POS)** | Search medicines, cart, discount/tax, auto stock deduction (trigger), printable invoice |
| **3. Customers & Prescriptions** | Customer & doctor records, prescriptions, chronic refill reminders |
| **4. Alerts, Reports & Admin** | Expiry alerts (30/60/90 days), low-stock alerts, sales reports, top sellers, users, audit log |

## 🧠 DBMS Concepts Demonstrated
- **Normalization** up to 3NF (12 related tables)
- **Primary & Foreign Keys**, ON DELETE CASCADE / SET NULL
- **Joins** (INNER / LEFT) across medicines, batches, sales, customers
- **Triggers** — `trg_deduct_stock` (auto stock deduction), `trg_expiry_log` (expiry logging)
- **Stored Procedures** — `sp_create_sale`, `sp_finalize_sale`, `sp_expiry_check`
- **Views** — `v_low_stock`, `v_expiring_soon`
- **Transactions** — checkout commits or rolls back as a whole
- **Indexing** — primary keys + unique constraints

---

## 🛠️ Tech Stack
- **Backend:** Python 3 + Flask
- **Database:** MySQL 8
- **DB Connector:** mysql-connector-python
- **Frontend:** HTML5, CSS3, Bootstrap 5, Bootstrap Icons, Jinja2

---

## 🚀 How to Run on Localhost

### ✅ Prerequisites
Make sure these are installed before you start:
- **Python 3.8+** → check with `python --version`
- **MySQL 8** (or XAMPP / MySQL Workbench) and the MySQL server must be **running**
- **pip** (comes with Python)

---

### 1. Get the code
```bash
git clone https://github.com/Zohaib-Aziz-Panhwar/PharmaCare-.git
cd PharmaCare-
```

### 2. (Recommended) Create a virtual environment
```powershell
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
```

### 3. Install Python packages
```powershell
pip install -r requirements.txt
```

### 4. Create the database
Run this in the project folder (enter your MySQL password when asked):
```powershell
mysql -u root -p < database/schema.sql
```
This creates the `pharmacy_db` database with all **tables, triggers, stored
procedures, views and sample data**.

> Using XAMPP/Workbench instead? Just open `database/schema.sql` in the SQL
> editor and click **Run**.

### 5. Set your MySQL password (config)
Copy the template and add your own MySQL password:
```powershell
copy config.example.py config.py     # Windows
# cp config.example.py config.py     # macOS / Linux
```
Then open **config.py** and edit the password line:
```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "YOUR_MYSQL_PASSWORD_HERE",   # <-- your MySQL password
    "database": "pharmacy_db",
}
```
> `config.py` is git-ignored so your password is never uploaded to GitHub.

### 6. Run the app
```powershell
python app.py
```
Now open your browser at 👉 **http://127.0.0.1:5000**

---

### 🛠️ Troubleshooting
| Problem | Fix |
|---------|-----|
| `Access denied for user 'root'` | Wrong password in `config.py` |
| `Can't connect to MySQL server` | MySQL service is not running — start it |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| `Unknown database 'pharmacy_db'` | Re-run step 4 to create the database |

---

## 🔑 Demo Logins

| Username | Password   | Role        |
|----------|------------|-------------|
| admin    | admin123   | Admin       |
| pharma   | pharma123  | Pharmacist  |
| cashier  | cashier123 | Cashier     |

> On first run the app automatically replaces the demo passwords with secure hashes.

---

## 📁 Project Structure
```
DB_Project/
├── app.py                # Flask routes (all 4 modules)
├── db.py                 # MySQL helper functions
├── config.py             # DB + app settings (edit your password here)
├── requirements.txt
├── database/
│   └── schema.sql        # Full database: tables, triggers, procedures, views, sample data
├── static/
│   └── css/style.css     # Custom styling
└── templates/            # Jinja2 + Bootstrap pages
    ├── base.html         # Sidebar layout
    ├── login.html
    ├── dashboard.html
    ├── medicines.html  batches.html  suppliers.html
    ├── pos.html  invoice.html  sales.html
    ├── customers.html  doctors.html  prescriptions.html
    └── alerts.html  reports.html  users.html
```

---

## 👥 Group Members
1. **Zohaib Aziz** — Team Lead — Inventory & Supplier Management
2. **Abdullah Tariq** — Sales & Billing (POS)
3. **Fahad Hussain Soomro** — Customer & Prescription Management
4. **Haris Bin Arif** — Alerts, Reports & Admin Dashboard
