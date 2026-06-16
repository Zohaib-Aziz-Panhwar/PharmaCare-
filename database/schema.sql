-- ============================================================
-- Smart Pharmacy Management System
-- DBMS Lab Project - MySQL Schema
-- ------------------------------------------------------------
-- This script creates the full database:
--   1. Tables (normalized up to 3NF)
--   2. Views   (low-stock, expiring-soon)
--   3. Triggers (auto stock deduction, expiry logging)
--   4. Stored Procedures (billing checkout, expiry check)
--   5. Sample data so the app works right away
--
-- HOW TO RUN:
--   mysql -u root -p < schema.sql
-- ============================================================

DROP DATABASE IF EXISTS pharmacy_db;
CREATE DATABASE pharmacy_db;
USE pharmacy_db;

-- ============================================================
-- 1. USERS (role-based access: Admin, Pharmacist, Cashier)
-- ============================================================
CREATE TABLE users (
    user_id      INT AUTO_INCREMENT PRIMARY KEY,
    username     VARCHAR(50)  NOT NULL UNIQUE,
    password     VARCHAR(255) NOT NULL,            -- stored as a hash
    full_name    VARCHAR(100) NOT NULL,
    role         ENUM('Admin','Pharmacist','Cashier') NOT NULL DEFAULT 'Cashier',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 2. CATEGORIES  (e.g. Antibiotic, Painkiller, Syrup)
-- ============================================================
CREATE TABLE categories (
    category_id  INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(60) NOT NULL UNIQUE
);

-- ============================================================
-- 3. SUPPLIERS
-- ============================================================
CREATE TABLE suppliers (
    supplier_id    INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone          VARCHAR(20),
    email          VARCHAR(100),
    address        VARCHAR(255)
);

-- ============================================================
-- 4. MEDICINES
-- ============================================================
CREATE TABLE medicines (
    medicine_id          INT AUTO_INCREMENT PRIMARY KEY,
    name                 VARCHAR(120) NOT NULL,
    category_id          INT,
    dosage               VARCHAR(50),               -- e.g. "500mg", "10ml"
    unit_price           DECIMAL(10,2) NOT NULL DEFAULT 0,
    barcode              VARCHAR(50) UNIQUE,
    requires_prescription TINYINT(1) NOT NULL DEFAULT 0,
    reorder_level        INT NOT NULL DEFAULT 20,   -- low-stock threshold
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
        ON DELETE SET NULL
);

-- ============================================================
-- 5. BATCHES  (each medicine can have many batches / expiry dates)
-- ============================================================
CREATE TABLE batches (
    batch_id      INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id   INT NOT NULL,
    supplier_id   INT,
    batch_number  VARCHAR(50) NOT NULL,
    mfg_date      DATE,
    expiry_date   DATE NOT NULL,
    quantity      INT NOT NULL DEFAULT 0,
    received_date DATE DEFAULT (CURRENT_DATE),
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE SET NULL
);

-- ============================================================
-- 6. DOCTORS
-- ============================================================
CREATE TABLE doctors (
    doctor_id      INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    specialization VARCHAR(80),
    phone          VARCHAR(20),
    hospital       VARCHAR(120)
);

-- ============================================================
-- 7. CUSTOMERS
-- ============================================================
CREATE TABLE customers (
    customer_id   INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    phone         VARCHAR(20),
    email         VARCHAR(100),
    address       VARCHAR(255),
    medical_notes TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 8. PRESCRIPTIONS
-- ============================================================
CREATE TABLE prescriptions (
    prescription_id   INT AUTO_INCREMENT PRIMARY KEY,
    customer_id       INT NOT NULL,
    doctor_id         INT,
    prescription_date DATE NOT NULL,
    notes             TEXT,
    is_chronic        TINYINT(1) NOT NULL DEFAULT 0,   -- refill reminders
    next_refill_date  DATE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id)   REFERENCES doctors(doctor_id)     ON DELETE SET NULL
);

-- ============================================================
-- 9. SALES  (one bill / invoice per row)
-- ============================================================
CREATE TABLE sales (
    sale_id         INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT,
    user_id         INT,
    prescription_id INT,
    sale_date       DATETIME DEFAULT CURRENT_TIMESTAMP,
    subtotal        DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount        DECIMAL(10,2) NOT NULL DEFAULT 0,
    tax             DECIMAL(10,2) NOT NULL DEFAULT 0,
    total           DECIMAL(10,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (customer_id)     REFERENCES customers(customer_id)         ON DELETE SET NULL,
    FOREIGN KEY (user_id)         REFERENCES users(user_id)                 ON DELETE SET NULL,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(prescription_id) ON DELETE SET NULL
);

-- ============================================================
-- 10. SALE_ITEMS  (line items of each bill)
-- ============================================================
CREATE TABLE sale_items (
    sale_item_id  INT AUTO_INCREMENT PRIMARY KEY,
    sale_id       INT NOT NULL,
    medicine_id   INT NOT NULL,
    batch_id      INT NOT NULL,
    quantity      INT NOT NULL,
    unit_price    DECIMAL(10,2) NOT NULL,
    line_total    DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (sale_id)     REFERENCES sales(sale_id)         ON DELETE CASCADE,
    FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
    FOREIGN KEY (batch_id)    REFERENCES batches(batch_id)
);

-- ============================================================
-- 11. ACTIVITY_LOG  (audit trail)
-- ============================================================
CREATE TABLE activity_log (
    log_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT,
    action     VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- ============================================================
-- 12. EXPIRY_LOG  (written automatically by a trigger)
-- ============================================================
CREATE TABLE expiry_log (
    expiry_log_id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id      INT,
    medicine_name VARCHAR(120),
    expiry_date   DATE,
    note          VARCHAR(255),
    logged_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
--  VIEWS
-- ============================================================

-- Low-stock view: total quantity per medicine vs. its reorder level
CREATE OR REPLACE VIEW v_low_stock AS
SELECT  m.medicine_id,
        m.name,
        m.reorder_level,
        COALESCE(SUM(b.quantity), 0) AS total_stock
FROM    medicines m
LEFT JOIN batches b ON b.medicine_id = m.medicine_id
GROUP BY m.medicine_id, m.name, m.reorder_level
HAVING total_stock <= m.reorder_level;

-- Expiring-soon view: batches expiring within the next 90 days
CREATE OR REPLACE VIEW v_expiring_soon AS
SELECT  b.batch_id,
        m.name AS medicine_name,
        b.batch_number,
        b.expiry_date,
        b.quantity,
        DATEDIFF(b.expiry_date, CURRENT_DATE) AS days_left
FROM    batches b
JOIN    medicines m ON m.medicine_id = b.medicine_id
WHERE   b.quantity > 0
  AND   b.expiry_date <= DATE_ADD(CURRENT_DATE, INTERVAL 90 DAY)
ORDER BY b.expiry_date ASC;


-- ============================================================
--  TRIGGERS
-- ============================================================
DELIMITER //

-- (a) Auto-deduct stock from a batch when a sale item is inserted
CREATE TRIGGER trg_deduct_stock
AFTER INSERT ON sale_items
FOR EACH ROW
BEGIN
    UPDATE batches
       SET quantity = quantity - NEW.quantity
     WHERE batch_id = NEW.batch_id;
END//

-- (b) Log a batch when it is added already-expired or near expiry
CREATE TRIGGER trg_expiry_log
AFTER INSERT ON batches
FOR EACH ROW
BEGIN
    IF NEW.expiry_date <= DATE_ADD(CURRENT_DATE, INTERVAL 30 DAY) THEN
        INSERT INTO expiry_log (batch_id, medicine_name, expiry_date, note)
        SELECT NEW.batch_id, m.name, NEW.expiry_date,
               'Batch added with expiry within 30 days'
        FROM medicines m
        WHERE m.medicine_id = NEW.medicine_id;
    END IF;
END//

DELIMITER ;


-- ============================================================
--  STORED PROCEDURES
-- ============================================================
DELIMITER //

-- sp_expiry_check: returns batches expiring within N days
CREATE PROCEDURE sp_expiry_check(IN p_days INT)
BEGIN
    SELECT b.batch_id, m.name AS medicine_name, b.batch_number,
           b.expiry_date, b.quantity,
           DATEDIFF(b.expiry_date, CURRENT_DATE) AS days_left
    FROM   batches b
    JOIN   medicines m ON m.medicine_id = b.medicine_id
    WHERE  b.quantity > 0
      AND  b.expiry_date <= DATE_ADD(CURRENT_DATE, INTERVAL p_days DAY)
    ORDER BY b.expiry_date ASC;
END//

-- sp_create_sale: creates an empty bill inside a transaction and
-- returns the new sale_id. Line items are added by the app, then
-- sp_finalize_sale totals everything up.
CREATE PROCEDURE sp_create_sale(
    IN  p_customer_id     INT,
    IN  p_user_id         INT,
    IN  p_prescription_id INT,
    OUT p_sale_id         INT
)
BEGIN
    INSERT INTO sales (customer_id, user_id, prescription_id)
    VALUES (NULLIF(p_customer_id,0), p_user_id, NULLIF(p_prescription_id,0));
    SET p_sale_id = LAST_INSERT_ID();
END//

-- sp_finalize_sale: recalculates totals for a bill given a discount %
-- and a tax %. Demonstrates aggregation + update in one procedure.
CREATE PROCEDURE sp_finalize_sale(
    IN p_sale_id      INT,
    IN p_discount_pct DECIMAL(5,2),
    IN p_tax_pct      DECIMAL(5,2)
)
BEGIN
    DECLARE v_subtotal DECIMAL(10,2) DEFAULT 0;
    DECLARE v_discount DECIMAL(10,2);
    DECLARE v_tax      DECIMAL(10,2);

    SELECT COALESCE(SUM(line_total),0) INTO v_subtotal
    FROM   sale_items WHERE sale_id = p_sale_id;

    SET v_discount = v_subtotal * (p_discount_pct/100);
    SET v_tax      = (v_subtotal - v_discount) * (p_tax_pct/100);

    UPDATE sales
       SET subtotal = v_subtotal,
           discount = v_discount,
           tax      = v_tax,
           total    = v_subtotal - v_discount + v_tax
     WHERE sale_id = p_sale_id;
END//

DELIMITER ;


-- ============================================================
--  SAMPLE DATA
-- ============================================================

-- Users  (all passwords below are the plain word shown; the Flask app
-- seeds proper hashes on first run, but these let SQL-only testing work.)
-- Default logins ->  admin/admin123 , pharma/pharma123 , cashier/cashier123
INSERT INTO users (username, password, full_name, role) VALUES
('admin',   'admin123',   'Zohaib Aziz',   'Admin'),
('pharma',  'pharma123',  'Fahad Hussain', 'Pharmacist'),
('cashier', 'cashier123', 'Abdullah Tariq','Cashier');

INSERT INTO categories (name) VALUES
('Antibiotic'), ('Painkiller'), ('Syrup'), ('Vitamin'), ('Antacid'), ('Antiseptic');

INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES
('MediSource Ltd', 'Imran Khan',  '0300-1112233', 'sales@medisource.com', 'Karachi'),
('PharmaWorld',    'Sana Malik',  '0301-4445566', 'info@pharmaworld.com', 'Lahore'),
('HealthLine Co.', 'Bilal Ahmed', '0302-7778899', 'contact@healthline.com','Islamabad');

INSERT INTO medicines (name, category_id, dosage, unit_price, barcode, requires_prescription, reorder_level) VALUES
('Panadol',        2, '500mg', 5.00,  '8901001', 0, 50),
('Amoxicillin',    1, '500mg', 12.00, '8901002', 1, 30),
('Brufen',         2, '400mg', 8.00,  '8901003', 0, 40),
('Cough Syrup',    3, '120ml', 90.00, '8901004', 0, 15),
('Vitamin C',      4, '1000mg',6.50,  '8901005', 0, 25),
('Gaviscon',       5, '300ml', 150.00,'8901006', 0, 10),
('Dettol',         6, '250ml', 200.00,'8901007', 0, 12),
('Augmentin',      1, '625mg', 25.00, '8901008', 1, 20);

-- Batches: a mix of healthy, low and soon-to-expire stock
INSERT INTO batches (medicine_id, supplier_id, batch_number, mfg_date, expiry_date, quantity) VALUES
(1, 1, 'PAN-A1', '2025-01-10', DATE_ADD(CURRENT_DATE, INTERVAL 400 DAY), 200),
(1, 1, 'PAN-A2', '2024-06-10', DATE_ADD(CURRENT_DATE, INTERVAL 25  DAY), 30),
(2, 2, 'AMX-B1', '2025-02-01', DATE_ADD(CURRENT_DATE, INTERVAL 300 DAY), 25),
(3, 1, 'BRU-C1', '2025-03-15', DATE_ADD(CURRENT_DATE, INTERVAL 200 DAY), 60),
(4, 3, 'CSY-D1', '2025-01-20', DATE_ADD(CURRENT_DATE, INTERVAL 70  DAY), 18),
(5, 2, 'VTC-E1', '2025-04-01', DATE_ADD(CURRENT_DATE, INTERVAL 500 DAY), 8),
(6, 3, 'GAV-F1', '2025-02-10', DATE_ADD(CURRENT_DATE, INTERVAL 60  DAY), 5),
(7, 1, 'DET-G1', '2025-03-01', DATE_ADD(CURRENT_DATE, INTERVAL 600 DAY), 40),
(8, 2, 'AUG-H1', '2024-12-01', DATE_ADD(CURRENT_DATE, INTERVAL 15  DAY), 22);

INSERT INTO doctors (name, specialization, phone, hospital) VALUES
('Dr. Ayesha Siddiqui', 'General Physician', '0345-1234567', 'City Hospital'),
('Dr. Usman Raza',      'Cardiologist',      '0346-2345678', 'Heart Care Center'),
('Dr. Hina Tariq',      'Pediatrician',      '0347-3456789', 'Children Clinic');

INSERT INTO customers (name, phone, email, address, medical_notes) VALUES
('Ali Hassan',    '0311-1111111', 'ali@example.com',   'Gulshan, Karachi', 'Diabetic'),
('Maria Khan',    '0312-2222222', 'maria@example.com', 'Model Town, Lahore','Allergic to Penicillin'),
('Saad Mehmood',  '0313-3333333', 'saad@example.com',  'F-8, Islamabad',    'Hypertension');

INSERT INTO prescriptions (customer_id, doctor_id, prescription_date, notes, is_chronic, next_refill_date) VALUES
(1, 1, CURRENT_DATE, 'Take Amoxicillin twice daily for 7 days', 0, NULL),
(3, 2, CURRENT_DATE, 'Monthly BP medication', 1, DATE_ADD(CURRENT_DATE, INTERVAL 5 DAY)),
(2, 3, CURRENT_DATE, 'Augmentin course for child', 0, NULL);

-- A sample completed sale so reports are not empty
INSERT INTO sales (customer_id, user_id, prescription_id, subtotal, discount, tax, total)
VALUES (1, 3, NULL, 100.00, 5.00, 9.50, 104.50);
INSERT INTO sale_items (sale_id, medicine_id, batch_id, quantity, unit_price, line_total)
VALUES (1, 1, 1, 20, 5.00, 100.00);

SELECT 'Database created successfully!' AS status;
