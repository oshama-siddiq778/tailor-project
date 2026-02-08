from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "tailor.db")
THERMAL_WIDTH = 80 * mm   # 80mm paper width

app = Flask(__name__)
_db_ready = False


UPLOAD_FOLDER = os.path.join(APP_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

REQ_ICON_FOLDER = os.path.join(APP_DIR, "static", "req_icons")
os.makedirs(REQ_ICON_FOLDER, exist_ok=True)
app.config["REQ_ICON_FOLDER"] = REQ_ICON_FOLDER


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()

    #Salary
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS salaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL,
            staff_no TEXT NOT NULL,
            shift_no TEXT NOT NULL,
            salary_amount REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (expense_id) REFERENCES expenses (id)
        )
        """
    )

    #Expenses
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_no TEXT UNIQUE,
            expense_name TEXT NOT NULL,
            amount REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            label TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            neck REAL,
            chest REAL,
            waist REAL,
            hip REAL,
            shoulder REAL,
            sleeve REAL,
            length REAL,
            cuff REAL,
            inseam REAL,
            outseam REAL,
            thigh REAL,
            knee REAL,
            bottom REAL,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            due_date TEXT,
            status TEXT NOT NULL,
            priority TEXT NOT NULL,
            assigned_team TEXT,
            assigned_tailor TEXT,
            notes TEXT,
            advance_amount REAL,
            total_amount REAL,
            paid_at TEXT,
            delivered_at TEXT,
            completed_at TEXT,
            picked_up_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            qty INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
        """
    )

    # cur.execute(
    #     """
    #     CREATE TABLE IF NOT EXISTS tailors (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         name TEXT NOT NULL,
    #         team TEXT NOT NULL
    #     )
    #     """
    # )
    cur.execute(
    """
        CREATE TABLE IF NOT EXISTS tailors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tailor_code TEXT UNIQUE,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        phone TEXT NOT NULL,
        status TEXT NOT NULL,
        team TEXT
    )
    """
)

    cur.execute("PRAGMA table_info(tailors)")
    existing_columns = [row[1] for row in cur.fetchall()]

    if "tailor_code" not in existing_columns:
        cur.execute("ALTER TABLE tailors ADD COLUMN tailor_code TEXT")

    if "role" not in existing_columns:
        cur.execute("ALTER TABLE tailors ADD COLUMN role TEXT")

    if "phone" not in existing_columns:
        cur.execute("ALTER TABLE tailors ADD COLUMN phone TEXT")

    if "status" not in existing_columns:
        cur.execute("ALTER TABLE tailors ADD COLUMN status TEXT")

    if "team" not in existing_columns:
        cur.execute("ALTER TABLE tailors ADD COLUMN team TEXT")

    cur.execute("UPDATE tailors SET status = 'Active' WHERE status IS NULL")
    cur.execute(
        "UPDATE tailors SET role = team WHERE role IS NULL AND team IS NOT NULL"
    )
    cur.execute("SELECT id FROM tailors WHERE tailor_code IS NULL ORDER BY id ASC")
    for row in cur.fetchall():
        cur.execute(
            "UPDATE tailors SET tailor_code = ? WHERE id = ?",
            (f"TLR{row['id']:03d}", row["id"]),
        )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_code TEXT UNIQUE,
            name TEXT NOT NULL,
            supplier TEXT,
            qty INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT,
            uom_id INTEGER,
            FOREIGN KEY (uom_id) REFERENCES uoms (id)
        )
        """
    )

    cur.execute("PRAGMA table_info(inventory)")
    inventory_columns = [row[1] for row in cur.fetchall()]
    if "inventory_code" not in inventory_columns:
        cur.execute("ALTER TABLE inventory ADD COLUMN inventory_code TEXT")
    if "uom_id" not in inventory_columns:
        cur.execute("ALTER TABLE inventory ADD COLUMN uom_id INTEGER")
    if "updated_at" not in inventory_columns:
        cur.execute("ALTER TABLE inventory ADD COLUMN updated_at TEXT")

    cur.execute("SELECT id FROM inventory WHERE inventory_code IS NULL ORDER BY id ASC")
    for row in cur.fetchall():
        cur.execute(
            "UPDATE inventory SET inventory_code = ? WHERE id = ?",
            (f"INV{row['id']:04d}", row["id"]),
        )
    cur.execute("UPDATE inventory SET updated_at = ? WHERE updated_at IS NULL", (now_str(),))

    cur.execute("PRAGMA table_info(orders)")
    order_columns = [row[1] for row in cur.fetchall()]
    if "advance_amount" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN advance_amount REAL")
    if "total_amount" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN total_amount REAL")
    if "paid_at" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN paid_at TEXT")
    if "delivered_at" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN delivered_at TEXT")
    if "completed_at" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN completed_at TEXT")
    if "picked_up_at" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN picked_up_at TEXT")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            measurement_type TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(category_id, name),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS measurement_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            subcategory_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (subcategory_id) REFERENCES subcategories (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS measurement_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcategory_id INTEGER NOT NULL,
            field_key TEXT NOT NULL,
            field_label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE(subcategory_id, field_key),
            FOREIGN KEY (subcategory_id) REFERENCES subcategories (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS requirement_icons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            filename TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_code TEXT UNIQUE,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vendor_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            material_name TEXT NOT NULL,
            qty REAL NOT NULL,
            uom_id INTEGER,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            purchased_at TEXT NOT NULL,
            FOREIGN KEY (vendor_id) REFERENCES vendors (id),
            FOREIGN KEY (uom_id) REFERENCES uoms (id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS uoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """
    )

    # cur.execute("SELECT COUNT(*) FROM tailors")
    # if cur.fetchone()[0] == 0:
    #     for i in range(1, 6):
    #         cur.execute(
    #             "INSERT INTO tailors (name, team) VALUES (?, ?)",
    #             (f"Shirt Tailor {i}", "Shirt"),
    #         )

    cur.execute("SELECT COUNT(*) FROM tailors")
    if cur.fetchone()[0] == 0:
        code_counter = 1
        for i in range(1, 6):
            cur.execute(
                """
                INSERT INTO tailors (tailor_code, name, role, phone, status, team)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"TLR{code_counter:03d}",
                    f"Shirt Tailor {i}",
                    "Shirt",
                    f"9000000{code_counter:02d}",
                    "Active",
                    "Shirt",
                ),
            )
            code_counter += 1
        for i in range(1, 6):
            cur.execute(
                """
                INSERT INTO tailors (tailor_code, name, role, phone, status, team)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"TLR{code_counter:03d}",
                    f"Pant Tailor {i}",
                    "Pant",
                    f"9000000{code_counter:02d}",
                    "Active",
                    "Pant",
                ),
            )
            code_counter += 1


        # for i in range(1, 6):
        #     cur.execute(
        #         "INSERT INTO tailors (name, team) VALUES (?, ?)",
        #         (f"Pant Tailor {i}", "Pant"),
        #     )

    cur.execute("SELECT COUNT(*) FROM inventory")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id FROM uoms ORDER BY id ASC LIMIT 1")
        default_uom = cur.fetchone()
        default_uom_id = default_uom["id"] if default_uom else None
        sample_inventory = [
            ("Italian Cotton - Navy", "Milano Textiles", 24, default_uom_id),
            ("Linen Blend - Sand", "Coastal Looms", 10, default_uom_id),
            ("Premium Buttons - Pearl", "ButtonWorks", 80, default_uom_id),
            ("Zipper 12in - Black", "Metro Trims", 18, default_uom_id),
            ("Thread - White 40wt", "StitchPro", 55, default_uom_id),
            ("Thread - Charcoal 40wt", "StitchPro", 14, default_uom_id),
        ]
        cur.executemany(
            """
            INSERT INTO inventory (name, supplier, qty, uom_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(name, supplier, qty, uom_id, now_str()) for name, supplier, qty, uom_id in sample_inventory],
        )

    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO categories (name, measurement_type) VALUES (?, ?)",
            [("Shirt", "Shirt"), ("Pant", "Pant")],
        )

    cur.execute("SELECT id, name FROM categories")
    category_map = {row["name"]: row["id"] for row in cur.fetchall()}
    if category_map.get("Shirt"):
        cur.execute("SELECT COUNT(*) FROM subcategories WHERE category_id = ?", (category_map["Shirt"],))
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO subcategories (category_id, name) VALUES (?, ?)",
                [
                    (category_map["Shirt"], "Full Hand"),
                    (category_map["Shirt"], "Half Hand"),
                ],
            )
    if category_map.get("Pant"):
        cur.execute("SELECT COUNT(*) FROM subcategories WHERE category_id = ?", (category_map["Pant"],))
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO subcategories (category_id, name) VALUES (?, ?)",
                [
                    (category_map["Pant"], "Trousers"),
                    (category_map["Pant"], "Boxers"),
                ],
            )

    cur.execute("SELECT COUNT(*) FROM uoms")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO uoms (name) VALUES (?)",
            [("KG",), ("Meters",), ("Pieces",), ("Bits",)],
        )

    cur.execute("SELECT id FROM uoms ORDER BY id ASC LIMIT 1")
    default_uom = cur.fetchone()
    if default_uom:
        cur.execute(
            "UPDATE inventory SET uom_id = ? WHERE uom_id IS NULL",
            (default_uom["id"],),
        )


    cur.execute("SELECT COUNT(*) FROM customers")
    if cur.fetchone()[0] == 0:
        sample_customers = [
            ("Arjun Mehta", "555-0101", "Prefers slim fit; pickup after 6pm"),
            ("Maya Patel", "555-0112", "Allergic to wool blends"),
            ("Rohan Iyer", "555-0124", "Prefers contrast stitching"),
            ("Leena Roy", "555-0138", "VIP client; rush orders"),
            ("Daniel Brooks", "555-0147", "Shorter sleeves by 1/2 inch"),
        ]
        cur.executemany(
            """
            INSERT INTO customers (name, phone, notes, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [(name, phone, notes, now_str()) for name, phone, notes in sample_customers],
        )

    cur.execute("SELECT COUNT(*) FROM orders")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, phone FROM customers ORDER BY id ASC")
        customer_rows = cur.fetchall()
        customer_ids = {row["phone"]: row["id"] for row in customer_rows}
        sample_orders = [
            ("555-0101", "2026-02-10", "In progress", "High", "Shirt", "Shirt Tailor 2", "Requirements: Pockets, Contrast Stitch"),
            ("555-0112", "2026-02-14", "Pending", "Normal", "Pant", "Pant Tailor 1", "Requirements: Pleats"),
            ("555-0124", "2026-02-08", "Ready", "Urgent", "Mixed", "Shirt Tailor 4", "Requirements: Embroidery, Extra Buttons"),
            ("555-0138", "2026-02-12", "In progress", "High", "Shirt", "Shirt Tailor 1", "VIP rush order"),
            ("555-0147", None, "Pending", "Normal", None, None, None),
        ]
        for phone, due_date, status, priority, team, tailor, notes in sample_orders:
            customer_id = customer_ids.get(phone)
            if not customer_id:
                continue
            cur.execute(
                """
                INSERT INTO orders (
                    customer_id, due_date, status, priority,
                    assigned_team, assigned_tailor, notes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer_id,
                    due_date,
                    status,
                    priority,
                    team,
                    tailor,
                    notes,
                    now_str(),
                ),
            )
            order_id = cur.lastrowid
            if phone == "555-0101":
                items = [("Shirt", 2, "Navy cotton, French cuffs")]
            elif phone == "555-0112":
                items = [("Pant", 1, "Sand linen blend, pleated")]
            elif phone == "555-0124":
                items = [("Shirt", 1, "Embroidery monogram"), ("Pant", 1, "Charcoal wool")]
            elif phone == "555-0138":
                items = [("Shirt", 3, "White poplin, slim fit")]
            else:
                items = [("Pant", 1, "Standard fit")]
            cur.executemany(
                "INSERT INTO order_items (order_id, item_type, qty, notes) VALUES (?, ?, ?, ?)",
                [(order_id, item, qty, note) for item, qty, note in items],
            )

    cur.execute("SELECT COUNT(*) FROM measurements")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, phone FROM customers ORDER BY id ASC")
        customer_rows = cur.fetchall()
        customer_ids = {row["phone"]: row["id"] for row in customer_rows}
        measurements = [
            ("555-0101", "Shirt", dict(neck="15 1/2", chest="40", waist="36", hip="41", shoulder="18", sleeve="33", length="30", cuff="9")),
            ("555-0101", "Pant", dict(waist="34", hip="40", inseam="31", outseam="41", thigh="23", knee="16", bottom="14 1/2")),
            ("555-0112", "Pant", dict(waist="30", hip="38", inseam="30 1/2", outseam="40", thigh="22", knee="15 1/2", bottom="13")),
            ("555-0124", "Shirt", dict(neck="16", chest="42", waist="38", hip="43", shoulder="18 1/2", sleeve="34", length="31", cuff="9 1/2")),
        ]
        for phone, kind, fields in measurements:
            customer_id = customer_ids.get(phone)
            if not customer_id:
                continue
            create_measurement(customer_id, kind, fields, conn)

    conn.commit()
    conn.close()


@app.before_request
def ensure_db_ready() -> None:
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def generate_expense_no(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    cur.execute("SELECT expense_no FROM expenses ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()

    if row:
        last_num = int(row["expense_no"].split("-")[1])
        return f"EXP-{last_num + 1:04d}"

    return "EXP-0001"

def generate_expense_pdf_80mm(
    expense_no: str,
    name: str,
    amount: float,
    created_at: str,
    is_salary: bool = False,
    staff_no: str | None = None
):
    folder = os.path.join(APP_DIR, "static", "expense_pdfs")
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, f"{expense_no}.pdf")

    height = 140 * mm
    pdf = canvas.Canvas(file_path, pagesize=(THERMAL_WIDTH, height))

    y = height - 10 * mm

    def line(text, bold=False):
        nonlocal y
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 9)
        pdf.drawString(5 * mm, y, text)
        y -= 5 * mm

    # HEADER
    line("PREMIER TAILORS", bold=True)
    line("Salary Receipt" if is_salary else "Expense Receipt", bold=True)
    line("-" * 32)

    # INFO
    line(f"Receipt No : {expense_no}")
    line(f"Date       : {created_at}")

    if is_salary and staff_no:
        line(f"Staff No   : {staff_no}")

    line("-" * 32)

    # BODY
    if is_salary:
        line("Salary Paid To:")
        line(name)
        line(f"Salary Amount : Rs. {amount}", bold=True)
    else:
        line("Expense:")
        line(name)
        line(f"Amount : Rs. {amount}", bold=True)

    line("-" * 32)
    line("Thank you", bold=True)
    line("System Generated")

    pdf.showPage()
    pdf.save()

def upsert_customer(name: str, phone: str, notes: str | None) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM customers WHERE phone = ?", (phone,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE customers SET name = ?, notes = ? WHERE id = ?",
            (name, notes, row["id"]),
        )
        customer_id = row["id"]
    else:
        cur.execute(
            "INSERT INTO customers (name, phone, notes, created_at) VALUES (?, ?, ?, ?)",
            (name, phone, notes, now_str()),
        )
        customer_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(customer_id)


def create_measurement(
    customer_id: int,
    kind: str,
    fields: dict[str, str],
    conn: sqlite3.Connection | None = None,
) -> None:
    values = {
        "neck": fields.get("neck") or None,
        "chest": fields.get("chest") or None,
        "waist": fields.get("waist") or None,
        "hip": fields.get("hip") or None,
        "shoulder": fields.get("shoulder") or None,
        "sleeve": fields.get("sleeve") or None,
        "length": fields.get("length") or None,
        "cuff": fields.get("cuff") or None,
        "inseam": fields.get("inseam") or None,
        "outseam": fields.get("outseam") or None,
        "thigh": fields.get("thigh") or None,
        "knee": fields.get("knee") or None,
        "bottom": fields.get("bottom") or None,
        "notes": fields.get("notes") or None,
    }
    if not any(values.values()):
        return

    owns_conn = conn is None
    conn = conn or get_db()
    conn.execute(
        """
        INSERT INTO measurements (
            customer_id, kind, neck, chest, waist, hip, shoulder, sleeve, length, cuff,
            inseam, outseam, thigh, knee, bottom, notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            kind,
            values["neck"],
            values["chest"],
            values["waist"],
            values["hip"],
            values["shoulder"],
            values["sleeve"],
            values["length"],
            values["cuff"],
            values["inseam"],
            values["outseam"],
            values["thigh"],
            values["knee"],
            values["bottom"],
            values["notes"],
            now_str(),
        ),
    )
    if owns_conn:
        conn.commit()
        conn.close()


def generate_tailor_code() -> str:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tailors")
    count = cur.fetchone()[0] + 1
    conn.close()
    return f"TLR{count:03d}"


def generate_inventory_code(conn: sqlite3.Connection, name: str) -> str:
    base = "".join(ch for ch in name.upper() if ch.isalnum())
    prefix = base[:3] if len(base) >= 3 else (base or "INV")
    cur = conn.cursor()
    cur.execute(
        "SELECT inventory_code FROM inventory WHERE inventory_code LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}-%",),
    )
    row = cur.fetchone()
    if row and row["inventory_code"]:
        try:
            last_num = int(row["inventory_code"].split("-")[-1])
            return f"{prefix}-{last_num + 1:03d}"
        except ValueError:
            pass
    return f"{prefix}-001"


def generate_vendor_code(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    cur.execute("SELECT vendor_code FROM vendors ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row and row["vendor_code"] and row["vendor_code"].startswith("VND"):
        try:
            last_num = int(row["vendor_code"][3:])
            return f"VND{last_num + 1:04d}"
        except ValueError:
            pass
    cur.execute("SELECT COUNT(*) FROM vendors")
    count = cur.fetchone()[0] + 1
    return f"VND{count:04d}"

@app.route("/")
def dashboard():
    q = request.args.get("q", "").strip()
    conn = get_db()
    counts = {
        row["status"]: row["total"]
        for row in conn.execute(
            "SELECT status, COUNT(*) as total FROM orders GROUP BY status"
        ).fetchall()
    }
    totals = conn.execute(
        "SELECT COUNT(*) AS total_orders FROM orders"
    ).fetchone()
    total_items = conn.execute(
        "SELECT COALESCE(SUM(qty), 0) AS total_items FROM order_items"
    ).fetchone()
    stock_units = conn.execute(
        "SELECT COALESCE(SUM(qty), 0) AS stock_units FROM inventory"
    ).fetchone()
    low_stock_count = conn.execute(
        "SELECT COUNT(*) AS low_stock FROM inventory WHERE qty <= 5"
    ).fetchone()

    recent_orders = conn.execute(
        """
        SELECT orders.*, customers.name, customers.phone
        FROM orders
        JOIN customers ON customers.id = orders.customer_id
        ORDER BY orders.created_at DESC
        LIMIT 8
        """
    ).fetchall()

    active_orders = conn.execute(
        """
        SELECT orders.*, customers.name, customers.phone
        FROM orders
        JOIN customers ON customers.id = orders.customer_id
        WHERE orders.status != 'Completed'
        ORDER BY orders.due_date IS NULL, orders.due_date ASC, orders.created_at DESC
        LIMIT 8
        """
    ).fetchall()

    pickup_results = []
    if q:
        pickup_results = conn.execute(
            """
            SELECT customers.*,
                   orders.id AS order_id,
                   orders.status AS order_status,
                   orders.due_date AS order_due,
                   orders.notes AS order_notes
            FROM customers
            LEFT JOIN orders
              ON orders.id = (
                SELECT id FROM orders
                WHERE customer_id = customers.id
                ORDER BY created_at DESC
                LIMIT 1
              )
            WHERE customers.name LIKE ? OR customers.phone LIKE ?
            ORDER BY customers.name ASC
            LIMIT 6
            """,
            (f"%{q}%", f"%{q}%"),
        ).fetchall()

    low_stock = conn.execute(
        """
        SELECT * FROM inventory
        WHERE qty <= 5
        ORDER BY qty ASC
        LIMIT 6
        """
    ).fetchall()

    shirt_queue = conn.execute(
        """
        SELECT orders.id, orders.status, orders.due_date, customers.name, SUM(order_items.qty) as total_qty
        FROM orders
        JOIN customers ON customers.id = orders.customer_id
        JOIN order_items ON order_items.order_id = orders.id
        WHERE order_items.item_type = 'Shirt' AND orders.status != 'Completed'
        GROUP BY orders.id
        ORDER BY orders.due_date IS NULL, orders.due_date ASC
        LIMIT 6
        """
    ).fetchall()

    pant_queue = conn.execute(
        """
        SELECT orders.id, orders.status, orders.due_date, customers.name, SUM(order_items.qty) as total_qty
        FROM orders
        JOIN customers ON customers.id = orders.customer_id
        JOIN order_items ON order_items.order_id = orders.id
        WHERE order_items.item_type = 'Pant' AND orders.status != 'Completed'
        GROUP BY orders.id
        ORDER BY orders.due_date IS NULL, orders.due_date ASC
        LIMIT 6
        """
    ).fetchall()

    tailors = conn.execute("SELECT * FROM tailors ORDER BY team, name").fetchall()

    revenue = conn.execute(
        "SELECT COALESCE(SUM(total_amount), 0) AS revenue FROM orders WHERE paid_at IS NOT NULL"
    ).fetchone()
    spent = conn.execute(
        "SELECT COALESCE(SUM(total_price), 0) AS spent FROM vendor_purchases"
    ).fetchone()

    conn.close()
    return render_template(
        "dashboard.html",
        counts=counts,
        total_orders=int(totals["total_orders"]),
        total_items=int(total_items["total_items"]),
        stock_units=int(stock_units["stock_units"]),
        low_stock_count=int(low_stock_count["low_stock"]),
        recent_orders=recent_orders,
        low_stock=low_stock,
        shirt_queue=shirt_queue,
        pant_queue=pant_queue,
        tailors=tailors,
        active_orders=active_orders,
        pickup_results=pickup_results,
        q=q,
        revenue=float(revenue["revenue"]),
        spent=float(spent["spent"]),
    )


@app.route("/orders")
def orders():
    status = request.args.get("status", "").strip()
    conn = get_db()
    if status:
        rows = conn.execute(
            """
            SELECT orders.*, customers.name, customers.phone
            FROM orders
            JOIN customers ON customers.id = orders.customer_id
            WHERE orders.status = ?
            ORDER BY orders.created_at DESC
            """,
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT orders.*, customers.name, customers.phone
            FROM orders
            JOIN customers ON customers.id = orders.customer_id
            ORDER BY orders.created_at DESC
            """
        ).fetchall()
    conn.close()
    return render_template("orders.html", orders=rows, status=status)


@app.route("/orders/new", methods=["GET", "POST"])
def order_new():
    conn = get_db()
    tailors = conn.execute("SELECT * FROM tailors ORDER BY team, name").fetchall()
    categories = conn.execute(
        "SELECT * FROM categories ORDER BY name"
    ).fetchall()
    subcategories = conn.execute(
        "SELECT * FROM subcategories ORDER BY name"
    ).fetchall()
    measurement_fields = conn.execute(
        "SELECT * FROM measurement_fields ORDER BY subcategory_id, sort_order, field_label"
    ).fetchall()
    requirement_icons = conn.execute(
        "SELECT * FROM requirement_icons ORDER BY name"
    ).fetchall()
    field_map = {}
    for row in measurement_fields:
        field_map.setdefault(str(row["subcategory_id"]), []).append(
            {"key": row["field_key"], "label": row["field_label"]}
        )
    conn.close()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        notes = request.form.get("customer_notes", "").strip()
        if not name or not phone:
            return render_template(
                "order_new.html",
                tailors=tailors,
                categories=categories,
                subcategories=subcategories,
                measurement_fields=measurement_fields,
                measurement_field_map=field_map,
                requirement_icons=requirement_icons,
                error="Customer name and phone are required.",
            )

        customer_id = upsert_customer(name, phone, notes)
        measure_fields = [
            "neck",
            "chest",
            "waist",
            "hip",
            "shoulder",
            "sleeve",
            "length",
            "cuff",
            "inseam",
            "outseam",
            "thigh",
            "knee",
            "bottom",
            "notes",
        ]

        category_ids = request.form.getlist("measure_category_id")
        subcategory_ids = request.form.getlist("measure_subcategory_id")
        label_values = request.form.getlist("measure_label")
        values_by_field = {field: request.form.getlist(f"measure_{field}") for field in measure_fields}

        map_conn = get_db()
        cat_rows = map_conn.execute("SELECT id, name FROM categories").fetchall()
        sub_rows = map_conn.execute("SELECT id, name FROM subcategories").fetchall()
        category_map = {str(row["id"]): row["name"] for row in cat_rows}
        subcategory_map = {str(row["id"]): row["name"] for row in sub_rows}

        max_len = max(
            len(category_ids),
            len(subcategory_ids),
            len(label_values),
            max((len(items) for items in values_by_field.values()), default=0),
        )
        for idx in range(max_len):
            category_id = category_ids[idx].strip() if idx < len(category_ids) else ""
            if not category_id:
                continue
            subcategory_id = subcategory_ids[idx].strip() if idx < len(subcategory_ids) else ""
            category_name = category_map.get(category_id, "Category")
            subcategory_name = subcategory_map.get(subcategory_id, "")
            kind = f"{category_name} - {subcategory_name}" if subcategory_name else category_name

            payload = {}
            for field in measure_fields:
                items = values_by_field.get(field, [])
                payload[field] = items[idx].strip() if idx < len(items) and items[idx] else None

            label = label_values[idx].strip() if idx < len(label_values) and label_values[idx] else ""
            if label:
                notes = payload.get("notes") or ""
                label_note = f"Label: {label}"
                payload["notes"] = f"{label_note}\n{notes}".strip()

            create_measurement(customer_id, kind, payload, map_conn)

        map_conn.commit()
        map_conn.close()

        due_date = request.form.get("due_date", "").strip() or None
        priority = request.form.get("priority", "Normal")
        status = request.form.get("status", "Pending")
        assigned_tailor = request.form.get("assigned_tailor", "").strip() or None
        order_notes = request.form.get("order_notes", "").strip() or None
        requirements = [r.strip() for r in request.form.getlist("requirements") if r.strip()]
        if requirements:
            req_text = "Requirements: " + ", ".join(requirements)
            order_notes = f"{req_text}\n{order_notes}" if order_notes else req_text
        advance_amount = request.form.get("advance_amount", "").strip()
        total_amount = request.form.get("total_amount", "").strip()
        advance_value = float(advance_amount) if advance_amount else None
        total_value = float(total_amount) if total_amount else None

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO orders (
                customer_id, due_date, status, priority,
                assigned_team, assigned_tailor, notes,
                advance_amount, total_amount, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                due_date,
                status,
                priority,
                assigned_tailor,
                order_notes,
                advance_value,
                total_value,
                now_str(),
            ),
        )
        order_id = cur.lastrowid

        item_types = request.form.getlist("item_type")
        item_qtys = request.form.getlist("item_qty")
        item_notes = request.form.getlist("item_notes")
        for item_type, qty, note in zip(item_types, item_qtys, item_notes, strict=False):
            item_type = item_type.strip()
            if not item_type:
                continue
            qty_value = int(qty) if qty.strip().isdigit() else 1
            cur.execute(
                "INSERT INTO order_items (order_id, item_type, qty, notes) VALUES (?, ?, ?, ?)",
                (order_id, item_type, qty_value, note.strip() or None),
            )

        files = request.files.getlist("order_images")
        labels = request.form.getlist("image_labels")
        seen = set()
        for i, file in enumerate(files):
            if not file or not file.filename:
                continue
            key = (file.filename, file.content_length)
            if key in seen:
                continue
            seen.add(key)
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            label = labels[i] if i < len(labels) else ""
            cur.execute(
                "INSERT INTO order_images (order_id, filename, label) VALUES (?, ?, ?)",
                (order_id, filename, label),
            )

        conn.commit()
        conn.close()
        return redirect(url_for("order_detail", order_id=order_id))

    return render_template(
        "order_new.html",
        tailors=tailors,
        categories=categories,
        subcategories=subcategories,
        measurement_fields=measurement_fields,
        measurement_field_map=field_map,
        requirement_icons=requirement_icons,
    )

@app.route("/expense")
def expense_dashboard():
    filter_type = request.args.get("type", "all")  # all | expense | salary
    conn = get_db()

    total_expense = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses"
    ).fetchone()[0]

    total_salary = conn.execute(
        "SELECT COALESCE(SUM(salary_amount), 0) FROM salaries"
    ).fetchone()[0]

    base_query = """
        SELECT e.id,
               e.expense_no,
               e.expense_name,
               e.amount,
               e.created_at,
               s.staff_no,
               s.shift_no,
               s.salary_amount
        FROM expenses e
        LEFT JOIN salaries s ON s.expense_id = e.id
    """

    if filter_type == "salary":
        base_query += " WHERE s.id IS NOT NULL"
    elif filter_type == "expense":
        base_query += " WHERE s.id IS NULL"

    base_query += " ORDER BY e.created_at DESC"

    expenses = conn.execute(base_query).fetchall()
    conn.close()

    return render_template(
        "expense_dashboard.html",
        total_expense=total_expense,
        total_salary=total_salary,
        expenses=expenses,
        filter_type=filter_type
    )

@app.route("/expense/add", methods=["GET", "POST"])
def expense_add():
    conn = get_db()

    if request.method == "POST":
        name = request.form.get("expense_name", "").strip()
        expense_amount = request.form.get("expense_amount", "").strip()
        salary_amount = request.form.get("salary_amount", "").strip()
        is_salary = request.form.get("is_salary") == "1"

        expense_no = generate_expense_no(conn)

        # ✅ PRIORITY VALIDATION
        if not name:
            return render_template(
                "expense_add.html",
                error="Expense name is required",
                expense_no=expense_no
            )

        if is_salary:
            if not salary_amount:
                return render_template(
                    "expense_add.html",
                    error="Salary amount is required",
                    expense_no=expense_no
                )
            final_amount = float(salary_amount)
        else:
            if not expense_amount:
                return render_template(
                    "expense_add.html",
                    error="Expense amount is required",
                    expense_no=expense_no
                )
            final_amount = float(expense_amount)

        created_at = now_str()
        cur = conn.cursor()

        # ✅ EXPENSE INSERT (single source of truth)
        cur.execute(
            """
            INSERT INTO expenses (expense_no, expense_name, amount, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (expense_no, name, final_amount, created_at),
        )
        expense_id = cur.lastrowid

        # ✅ SALARY INSERT ONLY WHEN CHECKED
        if is_salary:
            staff_no = request.form.get("staff_no") or "-"
            shift_no = request.form.get("shift_no") or "-"   # ✅ prevents NOT NULL crash

            cur.execute(
                """
                INSERT INTO salaries (
                    expense_id, staff_no, shift_no, salary_amount, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    expense_id,
                    staff_no,
                    shift_no,
                    float(salary_amount),
                    created_at,
                ),
            )


        conn.commit()
        conn.close()

        # ✅ PRINT USES FINAL PRIORITY AMOUNT
        # generate_expense_pdf_80mm(expense_no, name, final_amount, created_at)
        generate_expense_pdf_80mm(
            expense_no,
            name,
            final_amount,
            created_at,
            is_salary=is_salary,
            staff_no=request.form.get("staff_no")
        )

        return redirect(url_for("expense_dashboard"))

    # expense_no = generate_expense_no(conn)
    # conn.close()
    # return render_template("expense_add.html", expense_no=expense_no)

    expense_no = generate_expense_no(conn)

    # ✅ FETCH STAFF LIST FOR DROPDOWN
    staffs = conn.execute(
        "SELECT tailor_code, name FROM tailors WHERE status = 'Active' ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template(
        "expense_add.html",
        expense_no=expense_no,
        staffs=staffs
    )


@app.route("/expense/<int:expense_id>/edit", methods=["GET", "POST"])
def expense_edit(expense_id: int):
    conn = get_db()
    expense = conn.execute(
        "SELECT * FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    salary = conn.execute(
        "SELECT * FROM salaries WHERE expense_id = ?",
        (expense_id,),
    ).fetchone()
    staffs = conn.execute(
        "SELECT tailor_code, name FROM tailors WHERE status = 'Active' ORDER BY name"
    ).fetchall()
    if not expense:
        conn.close()
        return redirect(url_for("expense_dashboard"))

    if request.method == "POST":
        name = request.form.get("expense_name", "").strip()
        amount = request.form.get("expense_amount", "").strip()
        if not name or not amount:
            conn.close()
            return render_template(
                "expense_edit.html",
                expense=expense,
                salary=salary,
                staffs=staffs,
                error="Name and amount are required.",
            )
        conn.execute(
            "UPDATE expenses SET expense_name = ?, amount = ? WHERE id = ?",
            (name, float(amount), expense_id),
        )
        if salary:
            staff_no = request.form.get("staff_no", "").strip() or "-"
            shift_no = salary["shift_no"] if salary["shift_no"] else "-"
            conn.execute(
                """
                UPDATE salaries
                SET staff_no = ?, shift_no = ?, salary_amount = ?
                WHERE expense_id = ?
                """,
                (staff_no, shift_no, float(amount), expense_id),
            )
        conn.commit()
        conn.close()
        return redirect(url_for("expense_dashboard"))

    conn.close()
    return render_template(
        "expense_edit.html",
        expense=expense,
        salary=salary,
        staffs=staffs,
    )


@app.route("/expense/<int:expense_id>/delete", methods=["POST"])
def expense_delete(expense_id: int):
    conn = get_db()
    conn.execute("DELETE FROM salaries WHERE expense_id = ?", (expense_id,))
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("expense_dashboard"))


@app.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        action = request.form.get("action", "")
        conn = get_db()
        cur = conn.cursor()

        if action == "add_category":
            name = request.form.get("category_name", "").strip()
            measurement_type = request.form.get("measurement_type", "Shirt").strip()
            if name:
                cur.execute(
                    "INSERT OR IGNORE INTO categories (name, measurement_type) VALUES (?, ?)",
                    (name, measurement_type),
                )

        elif action == "delete_category":
            category_id = request.form.get("category_id")
            if category_id:
                cur.execute(
                    "DELETE FROM measurement_labels WHERE category_id = ?",
                    (category_id,),
                )
                cur.execute(
                    "DELETE FROM subcategories WHERE category_id = ?",
                    (category_id,),
                )
                cur.execute("DELETE FROM categories WHERE id = ?", (category_id,))

        elif action == "add_subcategory":
            category_id = request.form.get("subcategory_category_id")
            name = request.form.get("subcategory_name", "").strip()
            if category_id and name:
                cur.execute(
                    "INSERT OR IGNORE INTO subcategories (category_id, name) VALUES (?, ?)",
                    (category_id, name),
                )

        elif action == "delete_subcategory":
            subcategory_id = request.form.get("subcategory_id")
            if subcategory_id:
                cur.execute(
                    "DELETE FROM measurement_labels WHERE subcategory_id = ?",
                    (subcategory_id,),
                )
                cur.execute("DELETE FROM subcategories WHERE id = ?", (subcategory_id,))

        elif action == "add_requirement":
            name = request.form.get("requirement_name", "").strip()
            icon = request.files.get("requirement_icon")
            if name and icon and icon.filename:
                filename = f"{uuid.uuid4().hex}_{secure_filename(icon.filename)}"
                filepath = os.path.join(app.config["REQ_ICON_FOLDER"], filename)
                icon.save(filepath)
                cur.execute(
                    "INSERT INTO requirement_icons (name, filename) VALUES (?, ?)",
                    (name, filename),
                )

        elif action == "delete_requirement":
            req_id = request.form.get("requirement_id")
            if req_id:
                row = cur.execute(
                    "SELECT filename FROM requirement_icons WHERE id = ?",
                    (req_id,),
                ).fetchone()
                if row:
                    try:
                        os.remove(os.path.join(app.config["REQ_ICON_FOLDER"], row["filename"]))
                    except OSError:
                        pass
                cur.execute("DELETE FROM requirement_icons WHERE id = ?", (req_id,))

        elif action == "add_uom":
            name = request.form.get("uom_name", "").strip()
            if name:
                cur.execute("INSERT OR IGNORE INTO uoms (name) VALUES (?)", (name,))

        elif action == "delete_uom":
            uom_id = request.form.get("uom_id")
            if uom_id:
                cur.execute("DELETE FROM uoms WHERE id = ?", (uom_id,))

        elif action == "save_fields":
            subcategory_id = request.form.get("fields_subcategory_id")
            field_keys = request.form.getlist("field_key")
            field_labels = request.form.getlist("field_label")
            if subcategory_id:
                cur.execute(
                    "DELETE FROM measurement_fields WHERE subcategory_id = ?",
                    (subcategory_id,),
                )
                used = set()
                for idx, (key, label) in enumerate(
                    zip(field_keys, field_labels, strict=False)
                ):
                    key = (key or "").strip()
                    label = (label or "").strip()
                    if not label:
                        continue
                    if not key:
                        base = "".join(ch for ch in label.lower() if ch.isalnum())
                        base = base[:12] if base else "field"
                        key = base
                        counter = 2
                        while key in used:
                            key = f"{base}{counter}"
                            counter += 1
                    used.add(key)
                    cur.execute(
                        """
                        INSERT INTO measurement_fields (subcategory_id, field_key, field_label, sort_order)
                        VALUES (?, ?, ?, ?)
                        """,
                        (subcategory_id, key, label, idx),
                    )

        conn.commit()
        conn.close()
        return redirect(url_for("categories"))

    conn = get_db()
    categories = conn.execute(
        "SELECT * FROM categories ORDER BY name"
    ).fetchall()
    subcategories = conn.execute(
        """
        SELECT s.*, c.name as category_name
        FROM subcategories s
        JOIN categories c ON c.id = s.category_id
        ORDER BY c.name, s.name
        """
    ).fetchall()
    measurement_fields = conn.execute(
        """
        SELECT f.*, s.name as subcategory_name, c.name as category_name
        FROM measurement_fields f
        JOIN subcategories s ON s.id = f.subcategory_id
        JOIN categories c ON c.id = s.category_id
        ORDER BY c.name, s.name, f.sort_order
        """
    ).fetchall()
    requirement_icons = conn.execute(
        "SELECT * FROM requirement_icons ORDER BY name"
    ).fetchall()
    uoms = conn.execute("SELECT * FROM uoms ORDER BY name").fetchall()
    field_map = {}
    for row in measurement_fields:
        field_map.setdefault(str(row["subcategory_id"]), {})[row["field_key"]] = row[
            "field_label"
        ]
    conn.close()

    return render_template(
        "categories.html",
        categories=categories,
        subcategories=subcategories,
        measurement_fields=measurement_fields,
        measurement_field_map=field_map,
        requirement_icons=requirement_icons,
        uoms=uoms,
    )

@app.route("/api/staff/<staff_code>")
def get_staff_name(staff_code):
    conn = get_db()
    row = conn.execute(
        "SELECT name FROM tailors WHERE tailor_code = ?",
        (staff_code,)
    ).fetchone()
    conn.close()

    return {"name": row["name"] if row else ""}



@app.route("/orders/<int:order_id>", methods=["GET", "POST"])
def order_detail(order_id: int):
    conn = get_db()
    if request.method == "POST":
        status = request.form.get("status", "Pending")
        assigned_tailor = request.form.get("assigned_tailor", "").strip() or None
        due_date = request.form.get("due_date", "").strip() or None
        notes = request.form.get("notes", "").strip() or None
        advance_amount = request.form.get("advance_amount", "").strip()
        total_amount = request.form.get("total_amount", "").strip()
        paid_flag = request.form.get("paid") == "1"
        picked_up_flag = request.form.get("picked_up") == "1"

        current = conn.execute(
            "SELECT paid_at, delivered_at, completed_at, picked_up_at FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        now = now_str()
        paid_at = current["paid_at"]
        completed_at = current["completed_at"]
        picked_up_at = current["picked_up_at"]
        if status == "Completed" and not completed_at:
            completed_at = now
        if paid_flag and not paid_at:
            paid_at = now
        if picked_up_flag and not picked_up_at:
            picked_up_at = now

        conn.execute(
            """
            UPDATE orders
            SET status = ?, assigned_tailor = ?, due_date = ?, notes = ?,
                advance_amount = ?, total_amount = ?, paid_at = ?,
                completed_at = ?, picked_up_at = ?
            WHERE id = ?
            """,
            (
                status,
                assigned_tailor,
                due_date,
                notes,
                float(advance_amount) if advance_amount else None,
                float(total_amount) if total_amount else None,
                paid_at,
                completed_at,
                picked_up_at,
                order_id,
            ),
        )
        conn.commit()

    order = conn.execute(
        """
        SELECT orders.*, customers.name, customers.phone, customers.notes AS customer_notes
        FROM orders
        JOIN customers ON customers.id = orders.customer_id
        WHERE orders.id = ?
        """,
        (order_id,),
    ).fetchone()
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
    ).fetchall()
    tailors = conn.execute("SELECT * FROM tailors ORDER BY team, name").fetchall()
    images = conn.execute(
        "SELECT filename, label FROM order_images WHERE order_id = ?",
        (order_id,),
    ).fetchall()
    conn.close()

    return render_template(
        "order_detail.html", order=order, items=items, tailors=tailors, images=images
    )

@app.route("/tailors")
def tailors():
    conn = get_db()

    rows = conn.execute(
        """
        SELECT 
            t.id,
            t.tailor_code,
            t.name,
            t.phone,
            t.status,
            o.id AS order_id,
            o.due_date
        FROM tailors t
        LEFT JOIN orders o ON o.assigned_tailor = t.name
        ORDER BY t.id DESC
        """
    ).fetchall()

    conn.close()
    return render_template("tailors.html", tailors=rows, title="Tailors")


@app.route("/tailors/add", methods=["GET", "POST"])
def tailor_add():
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            """
            INSERT INTO tailors (tailor_code, name, role, phone, status, team)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.form["tailor_code"],
                request.form["name"],
                request.form["role"],
                request.form["phone"],
                request.form["status"],
                request.form["role"],
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("tailors"))

    return render_template(
        "tailor_add.html",
        tailor_code=generate_tailor_code(),
        title="Add Tailor",
    )


@app.route("/tailors/edit/<int:tailor_id>", methods=["GET", "POST"])
def tailor_edit(tailor_id):
    conn = get_db()

    if request.method == "POST":
        conn.execute(
            """
            UPDATE tailors
            SET name = ?, role = ?, phone = ?, status = ?, team = ?
            WHERE id = ?
            """,
            (
                request.form["name"],
                request.form["role"],
                request.form["phone"],
                request.form["status"],
                request.form["role"],   # team = role (same logic as add)
                tailor_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("tailors"))

    tailor = conn.execute(
        "SELECT * FROM tailors WHERE id = ?",
        (tailor_id,),
    ).fetchone()

    conn.close()
    return render_template("tailor_edit.html", tailor=tailor, title="Edit Tailor")


@app.route("/customers")
def customers():
    q = request.args.get("q", "").strip()
    conn = get_db()
    if q:
        rows = conn.execute(
            """
            SELECT * FROM customers
            WHERE name LIKE ? OR phone LIKE ?
            ORDER BY name ASC
            """,
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM customers ORDER BY name ASC").fetchall()
    conn.close()
    return render_template("customers.html", customers=rows, q=q)


@app.route("/customers/<int:customer_id>", methods=["GET", "POST"])
def customer_detail(customer_id: int):
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        if name and phone:
            conn.execute(
                "UPDATE customers SET name = ?, phone = ? WHERE id = ?",
                (name, phone, customer_id),
            )
            conn.commit()

    customer = conn.execute(
        "SELECT * FROM customers WHERE id = ?", (customer_id,)
    ).fetchone()
    orders = conn.execute(
        """
        SELECT * FROM orders
        WHERE customer_id = ?
        ORDER BY created_at DESC
        """,
        (customer_id,),
    ).fetchall()
    conn.close()
    return render_template(
        "customer_detail.html",
        customer=customer,
        orders=orders,
    )


@app.route("/inventory", methods=["GET", "POST"])
def inventory():
    conn = get_db()
    if request.method == "POST":
        if request.form.get("action") == "update":
            conn.execute(
                """
                UPDATE inventory
                SET qty = ?, uom_id = ?, inventory_code = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(request.form.get("qty", "0") or 0),
                    int(request.form.get("uom_id") or 0) or None,
                    request.form.get("inventory_code", "").strip() or None,
                    now_str(),
                    int(request.form.get("item_id")),
                ),
            )
        conn.commit()

    items = conn.execute(
        """
        SELECT inventory.*, uoms.name AS uom_name
        FROM inventory
        LEFT JOIN uoms ON uoms.id = inventory.uom_id
        ORDER BY inventory.name ASC
        """
    ).fetchall()
    conn.close()
    return render_template("inventory.html", items=items)


@app.route("/inventory/add", methods=["GET", "POST"])
def inventory_add():
    conn = get_db()
    uoms = conn.execute("SELECT * FROM uoms ORDER BY name ASC").fetchall()
    vendors = conn.execute("SELECT * FROM vendors ORDER BY name ASC").fetchall()
    if request.method == "POST":
        names = request.form.getlist("item_name")
        vendors_in = request.form.getlist("item_vendor")
        qtys = request.form.getlist("item_qty")
        uoms_in = request.form.getlist("item_uom_id")

        has_item = any(name.strip() for name in names)
        if not has_item:
            conn.close()
            return render_template(
                "inventory_add.html",
                uoms=uoms,
                vendors=vendors,
                error="At least one item is required.",
            )

        for name, vendor, qty, uom_id in zip(names, vendors_in, qtys, uoms_in, strict=False):
            name = name.strip()
            if not name:
                continue
            inventory_code = generate_inventory_code(conn, name)
            conn.execute(
                """
                INSERT INTO inventory (inventory_code, name, supplier, qty, uom_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    inventory_code,
                    name,
                    vendor.strip() or None,
                    int(qty or 0),
                    int(uom_id or 0) or None,
                    now_str(),
                ),
            )

        conn.commit()
        conn.close()
        return redirect(url_for("inventory"))
    conn.close()
    return render_template("inventory_add.html", uoms=uoms, vendors=vendors)


@app.route("/inventory/<int:item_id>/edit", methods=["GET", "POST"])
def inventory_edit(item_id: int):
    conn = get_db()
    item = conn.execute(
        "SELECT * FROM inventory WHERE id = ?",
        (item_id,),
    ).fetchone()
    uoms = conn.execute("SELECT * FROM uoms ORDER BY name ASC").fetchall()
    vendors = conn.execute("SELECT * FROM vendors ORDER BY name ASC").fetchall()
    if not item:
        conn.close()
        return redirect(url_for("inventory"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            conn.close()
            return render_template(
                "inventory_edit.html",
                item=item,
                uoms=uoms,
                vendors=vendors,
                error="Item name is required.",
            )
        conn.execute(
            """
            UPDATE inventory
            SET name = ?, supplier = ?, qty = ?, uom_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                request.form.get("supplier", "").strip() or None,
                int(request.form.get("qty", "0") or 0),
                int(request.form.get("uom_id") or 0) or None,
                now_str(),
                item_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("inventory"))
    conn.close()
    return render_template("inventory_edit.html", item=item, uoms=uoms, vendors=vendors)


@app.route("/inventory/<int:item_id>/delete", methods=["POST"])
def inventory_delete(item_id: int):
    conn = get_db()
    conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("inventory"))


@app.route("/vendors")
def vendors():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT v.*,
               (SELECT MAX(purchased_at) FROM vendor_purchases WHERE vendor_id = v.id) AS last_order_at,
               (SELECT COALESCE(SUM(total_price), 0) FROM vendor_purchases WHERE vendor_id = v.id) AS spent
        FROM vendors v
        ORDER BY v.created_at DESC
        """
    ).fetchall()
    purchases = conn.execute(
        """
        SELECT vp.*,
               v.vendor_code,
               v.name AS vendor_name,
               uoms.name AS uom_name
        FROM vendor_purchases vp
        JOIN vendors v ON v.id = vp.vendor_id
        LEFT JOIN uoms ON uoms.id = vp.uom_id
        ORDER BY vp.purchased_at DESC
        """
    ).fetchall()
    conn.close()
    return render_template("vendors.html", vendors=rows, purchases=purchases)


@app.route("/vendors/add", methods=["GET", "POST"])
def vendors_add():
    conn = get_db()
    vendor_code = generate_vendor_code(conn)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            conn.close()
            return render_template(
                "vendors_add.html",
                vendor_code=vendor_code,
                error="Vendor name is required.",
            )
        conn.execute(
            """
            INSERT INTO vendors (vendor_code, name, phone, email, address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                vendor_code,
                name,
                request.form.get("phone", "").strip() or None,
                request.form.get("email", "").strip() or None,
                request.form.get("address", "").strip() or None,
                now_str(),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("vendors"))
    conn.close()
    return render_template("vendors_add.html", vendor_code=vendor_code)


@app.route("/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
def vendors_edit(vendor_id: int):
    conn = get_db()
    vendor = conn.execute(
        "SELECT * FROM vendors WHERE id = ?",
        (vendor_id,),
    ).fetchone()
    if not vendor:
        conn.close()
        return redirect(url_for("vendors"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            conn.close()
            return render_template(
                "vendors_edit.html",
                vendor=vendor,
                error="Vendor name is required.",
            )
        conn.execute(
            """
            UPDATE vendors
            SET name = ?, phone = ?, email = ?, address = ?
            WHERE id = ?
            """,
            (
                name,
                request.form.get("phone", "").strip() or None,
                request.form.get("email", "").strip() or None,
                request.form.get("address", "").strip() or None,
                vendor_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("vendors"))
    conn.close()
    return render_template("vendors_edit.html", vendor=vendor)


@app.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
def vendors_delete(vendor_id: int):
    conn = get_db()
    conn.execute("DELETE FROM vendor_purchases WHERE vendor_id = ?", (vendor_id,))
    conn.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("vendors"))


@app.route("/vendors/purchase", methods=["GET", "POST"])
def vendors_add_purchase():
    conn = get_db()
    vendors = conn.execute("SELECT * FROM vendors ORDER BY name ASC").fetchall()
    uoms = conn.execute("SELECT * FROM uoms ORDER BY name ASC").fetchall()
    if request.method == "POST":
        vendor_id = request.form.get("vendor_id")
        materials = request.form.getlist("material_name")
        qtys = request.form.getlist("qty")
        uom_ids = request.form.getlist("uom_id")
        prices = request.form.getlist("unit_price")

        if not vendor_id:
            conn.close()
            return render_template(
                "vendors_purchase_add.html",
                vendors=vendors,
                uoms=uoms,
                error="Vendor is required.",
            )

        has_item = any(name.strip() for name in materials)
        if not has_item:
            conn.close()
            return render_template(
                "vendors_purchase_add.html",
                vendors=vendors,
                uoms=uoms,
                error="At least one material is required.",
            )

        for name, qty, uom_id, price in zip(materials, qtys, uom_ids, prices, strict=False):
            name = name.strip()
            if not name:
                continue
            qty_val = float(qty or 0)
            price_val = float(price or 0)
            total_val = qty_val * price_val
            conn.execute(
                """
                INSERT INTO vendor_purchases (vendor_id, material_name, qty, uom_id, unit_price, total_price, purchased_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(vendor_id),
                    name,
                    qty_val,
                    int(uom_id or 0) or None,
                    price_val,
                    total_val,
                    now_str(),
                ),
            )

        conn.commit()
        conn.close()
        return redirect(url_for("vendors"))

    conn.close()
    return render_template("vendors_purchase_add.html", vendors=vendors, uoms=uoms)


@app.route("/vendors/purchase/<int:purchase_id>/edit", methods=["GET", "POST"])
def vendors_purchase_edit(purchase_id: int):
    conn = get_db()
    purchase = conn.execute(
        "SELECT * FROM vendor_purchases WHERE id = ?",
        (purchase_id,),
    ).fetchone()
    vendors = conn.execute("SELECT * FROM vendors ORDER BY name ASC").fetchall()
    uoms = conn.execute("SELECT * FROM uoms ORDER BY name ASC").fetchall()
    if not purchase:
        conn.close()
        return redirect(url_for("vendors"))
    if request.method == "POST":
        vendor_id = request.form.get("vendor_id")
        material_name = request.form.get("material_name", "").strip()
        qty_val = float(request.form.get("qty", "0") or 0)
        price_val = float(request.form.get("unit_price", "0") or 0)
        uom_id = int(request.form.get("uom_id") or 0) or None
        if not vendor_id or not material_name:
            conn.close()
            return render_template(
                "vendors_purchase_edit.html",
                purchase=purchase,
                vendors=vendors,
                uoms=uoms,
                error="Vendor and material are required.",
            )
        total_val = qty_val * price_val
        conn.execute(
            """
            UPDATE vendor_purchases
            SET vendor_id = ?, material_name = ?, qty = ?, uom_id = ?, unit_price = ?, total_price = ?
            WHERE id = ?
            """,
            (
                int(vendor_id),
                material_name,
                qty_val,
                uom_id,
                price_val,
                total_val,
                purchase_id,
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("vendors"))
    conn.close()
    return render_template(
        "vendors_purchase_edit.html",
        purchase=purchase,
        vendors=vendors,
        uoms=uoms,
    )


@app.route("/vendors/purchase/<int:purchase_id>/delete", methods=["POST"])
def vendors_purchase_delete(purchase_id: int):
    conn = get_db()
    conn.execute("DELETE FROM vendor_purchases WHERE id = ?", (purchase_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("vendors"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
