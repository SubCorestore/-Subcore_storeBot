import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = "shop.db"

# =========================================================
# DEFAULT PAYMENT INFORMATION
# =========================================================

DEFAULT_PAYMENT = {
    "binance_uid": "551481540",
    "usdt_trc20": "TQYfgwzEN8DFNE7LKPeppgSps2bcR5awFw",
    "usdt_bep20": "0xc1af1a00dca6c8012e4f88a4934dbf3a28a1102a",
}

CATEGORIES = {
    "ai": "🤖 AI Tools",
    "design": "🎨 Design & Video",
    "office": "💼 Office & Productivity",
    "entertainment": "📺 Entertainment",
    "software": "🛠️ Software",
    "other": "📦 Other",
}

DEFAULT_PRODUCTS = [
    ("CapCut Pro Personal", "design",
     "1 Month — $3.5\n6 Months — $12\n1 Year — $20\nCustomer Email — $20\nMonthly Renewal available",
     "Full Warranty"),
    ("ChatGPT Plus Personal", "ai", "Customer Email — 1 Month — $18", "Full Warranty"),
    ("ChatGPT Shared", "ai", "1 Month — $3.5", "Full Warranty"),
    ("Gemini Pro + Google Drive 5TB", "ai",
     "1 Month — $1\n12 Months — $3.5\nFamily Plan (5 Invites) — 12 Months — $8",
     "Full Warranty"),
    ("YouTube Premium", "entertainment",
     "1 Month — $1\n12 Months — $10\nMonthly Renewal available",
     "Full Warranty"),
    ("Amazon Prime", "entertainment", "1 Month — $2\n6 Months — $4", "Full Warranty"),
    ("Zoom Pro (100 Participants)", "office", "1 Month — $2.5", "Full Warranty"),
    ("Canva Pro", "design", "1 Month — $1\n12 Months — $7\nMonthly Renewal available", "Full Warranty"),
    ("Netflix Full Account", "entertainment", "1 Month — $7", "Full Warranty"),
    ("Claude Pro", "ai", "1 Month — $20", "Full Warranty"),
    ("Lovable Lite Personal", "ai", "12 Months — $15", "Full Warranty"),
    ("AutoCAD", "software", "1 Year — $6", "Full Warranty"),
    ("Microsoft Office 365 Readymade", "office", "1 Year — $6.4", "Full Warranty"),
    ("Microsoft Office 365 Personal Gmail", "office", "1 Year — $12", "Full Warranty"),
    ("Wondershare Recoverit", "software", "1 Year — $5", "Full Warranty"),
    ("Wondershare Filmora", "design", "1 Year — $3", "Full Warranty"),
]


# =========================================================
# DATABASE
# =========================================================

def db():
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price_info TEXT NOT NULL,
            warranty TEXT DEFAULT 'Full Warranty',
            photo_id TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product_id INTEGER,
            payment_method TEXT,
            status TEXT DEFAULT 'New',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Backward compatibility with the old orders table.
    cols = {r[1] for r in con.execute("PRAGMA table_info(orders)").fetchall()}
    if "payment_method" not in cols:
        con.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT")
    if "created_at" not in cols:
        con.execute("ALTER TABLE orders ADD COLUMN created_at TEXT")

    pcols = {r[1] for r in con.execute("PRAGMA table_info(products)").fetchall()}
    if "active" not in pcols:
        con.execute("ALTER TABLE products ADD COLUMN active INTEGER DEFAULT 1")

    for key, value in DEFAULT_PAYMENT.items():
        con.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value)
        )

    count = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        con.executemany(
            "INSERT INTO products(name,category,price_info,warranty) VALUES(?,?,?,?)",
            DEFAULT_PRODUCTS
        )

    con.commit()
    return con


db()


def setting(key):
    con = db()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row[0] if row else ""


def set_setting(key, value):
    con = db()
    con.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    con.commit()
    con.close()


# =========================================================
# SECURITY / HELPERS
# =========================================================

def is_admin(update: Update):
    return bool(
        ADMIN_ID and
        update.effective_user and
        update.effective_user.id == ADMIN_ID
    )


async def admin_only(update):
    if not is_admin(update):
        if update.callback_query:
            await update.callback_query.answer("⛔ Admin only.", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔ Admin only.")
        return False
    return True


def back_home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")]
    ])


# =========================================================
# CUSTOMER MENU
# =========================================================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ All Products", callback_data="all")],
        [
            InlineKeyboardButton("🤖 AI Tools", callback_data="cat_ai"),
            InlineKeyboardButton("🎨 Design & Video", callback_data="cat_design")
        ],
        [
            InlineKeyboardButton("💼 Office & Productivity", callback_data="cat_office"),
            InlineKeyboardButton("📺 Entertainment", callback_data="cat_entertainment")
        ],
        [
            InlineKeyboardButton("🛠️ Software", callback_data="cat_software"),
            InlineKeyboardButton("📦 Other Products", callback_data="cat_other")
        ],
        [
            InlineKeyboardButton("📦 My Orders", callback_data="myorders"),
            InlineKeyboardButton("💬 Support", callback_data="support")
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✨ Welcome to Our Digital Store ✨\n\n"
        "🛡️ Full Warranty Included\n"
        "⚡ Stable Access\n"
        "🚀 Fast Delivery & Dedicated Support\n\n"
        "Choose a category below:",
        reply_markup=main_menu()
    )


async def products_page(category=None, admin=False):
    con = db()
    if category:
        rows = con.execute(
            "SELECT id,name,active FROM products WHERE category=? ORDER BY id DESC",
            (category,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id,name,active FROM products ORDER BY id DESC"
        ).fetchall()
    con.close()

    buttons = []
    for pid, name, active in rows:
        if admin:
            icon = "🟢" if active else "🔴"
            buttons.append([InlineKeyboardButton(
                f"{icon} {name}", callback_data=f"ap_{pid}"
            )])
        elif active:
            buttons.append([InlineKeyboardButton(
                name, callback_data=f"product_{pid}"
            )])

    if admin:
        buttons.append([InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")])
    else:
        buttons.append([InlineKeyboardButton("⬅️ Main Menu", callback_data="home")])

    return InlineKeyboardMarkup(buttons)


async def show_product(query, pid):
    con = db()
    row = con.execute(
        "SELECT id,name,price_info,warranty,photo_id,active FROM products WHERE id=?",
        (pid,)
    ).fetchone()
    con.close()

    if not row or not row[5]:
        await query.answer("Product is unavailable.", show_alert=True)
        return

    _, name, price_info, warranty, photo_id, _ = row
    text = (
        f"🛍️ <b>{name}</b>\n\n"
        f"💰 {price_info}\n\n"
        f"🛡️ Warranty: {warranty}\n"
        f"⚡ Fast Delivery & Support"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Order Now", callback_data=f"order_{pid}")],
        [InlineKeyboardButton("⬅️ Products", callback_data="all")]
    ])

    if photo_id:
        await query.message.reply_photo(
            photo_id, caption=text, parse_mode="HTML", reply_markup=kb
        )
        try:
            await query.message.delete()
        except Exception:
            pass
    else:
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=kb
        )


# =========================================================
# PAYMENT
# =========================================================

def payment_menu(pid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 Binance", callback_data=f"pay_binance_{pid}")],
        [InlineKeyboardButton("🔴 USDT TRC20", callback_data=f"pay_trc20_{pid}")],
        [InlineKeyboardButton("🟢 USDT BEP20", callback_data=f"pay_bep20_{pid}")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"product_{pid}")]
    ])


def payment_details(method):
    if method == "binance":
        return (
            "🟡 <b>Binance Payment</b>\n\n"
            f"🆔 <b>Binance UID:</b>\n<code>{setting('binance_uid')}</code>\n\n"
            "⚠️ Send the exact amount, then submit your payment screenshot."
        )
    if method == "trc20":
        return (
            "🔴 <b>USDT TRC20 Payment</b>\n\n"
            f"📍 <b>Address:</b>\n<code>{setting('usdt_trc20')}</code>\n\n"
            "⚠️ Network must be TRC20. Then submit your payment screenshot."
        )
    if method == "bep20":
        return (
            "🟢 <b>USDT BEP20 Payment</b>\n\n"
            f"📍 <b>Address:</b>\n<code>{setting('usdt_bep20')}</code>\n\n"
            "⚠️ Network must be BEP20. Then submit your payment screenshot."
        )
    return "Payment method not found."


def payment_proof_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Send Payment Proof", callback_data="send_proof")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")]
    ])


# =========================================================
# ADMIN PANEL
# =========================================================

def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Products", callback_data="admin_products"),
            InlineKeyboardButton("💳 Payment", callback_data="admin_payment")
        ],
        [
            InlineKeyboardButton("🛒 Orders", callback_data="admin_orders"),
            InlineKeyboardButton("👥 Stats", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        ],
    ])


async def admin_command(update, context):
    if not await admin_only(update):
        return
    context.user_data.clear()
    await update.message.reply_text(
        "⚙️ <b>ADMIN PANEL</b>\n\nChoose an option:",
        parse_mode="HTML",
        reply_markup=admin_menu()
    )


async def admin_products_menu(query):
    await query.edit_message_text(
        "📦 <b>Product Management</b>\n\n"
        "🟢 = visible to customers\n"
        "🔴 = hidden from customers",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Product", callback_data="add_product")],
            [InlineKeyboardButton("✏️ Edit Product", callback_data="edit_products")],
            [InlineKeyboardButton("🟢/🔴 Enable / Disable", callback_data="toggle_products")],
            [InlineKeyboardButton("🗑️ Delete Product", callback_data="delete_products")],
            [InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")]
        ])
    )


async def admin_payment_menu(query):
    text = (
        "💳 <b>Payment Settings</b>\n\n"
        f"🟡 Binance UID:\n<code>{setting('binance_uid')}</code>\n\n"
        f"🔴 USDT TRC20:\n<code>{setting('usdt_trc20')}</code>\n\n"
        f"🟢 USDT BEP20:\n<code>{setting('usdt_bep20')}</code>"
    )
    await query.edit_message_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟡 Edit Binance UID", callback_data="set_binance_uid")],
            [InlineKeyboardButton("🔴 Edit TRC20", callback_data="set_usdt_trc20")],
            [InlineKeyboardButton("🟢 Edit BEP20", callback_data="set_usdt_bep20")],
            [InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")]
        ])
    )


async def admin_orders_menu(query):
    con = db()
    rows = con.execute("""
        SELECT o.id, p.name, o.username, o.payment_method, o.status, o.created_at
        FROM orders o
        LEFT JOIN products p ON p.id=o.product_id
        ORDER BY o.id DESC LIMIT 20
    """).fetchall()
    con.close()

    if not rows:
        text = "🛒 <b>Orders</b>\n\nNo orders yet."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")]])
    else:
        text = "🛒 <b>Recent Orders</b>\n\nTap an order:"
        buttons = []
        for oid, name, username, payment, status, created in rows:
            buttons.append([InlineKeyboardButton(
                f"#{oid} • {status} • {name[:20]}",
                callback_data=f"order_view_{oid}"
            )])
        buttons.append([InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")])
        kb = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


async def admin_stats(query):
    con = db()
    products = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    active = con.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0]
    orders = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    pending = con.execute(
        "SELECT COUNT(*) FROM orders WHERE status IN ('Payment Pending','Payment Proof Submitted')"
    ).fetchone()[0]
    con.close()

    await query.edit_message_text(
        "📊 <b>Store Statistics</b>\n\n"
        f"📦 Total Products: {products}\n"
        f"🟢 Active Products: {active}\n"
        f"🛒 Total Orders: {orders}\n"
        f"⏳ Pending Orders: {pending}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Admin Panel", callback_data="admin")]
        ])
    )


async def admin_product_list(query, action):
    con = db()
    rows = con.execute(
        "SELECT id,name,active FROM products ORDER BY id DESC"
    ).fetchall()
    con.close()

    buttons = []
    for pid, name, active in rows:
        if action == "edit":
            cb = f"edit_{pid}"
        elif action == "toggle":
            cb = f"toggle_{pid}"
        else:
            cb = f"delete_{pid}"
        icon = "🟢" if active else "🔴"
        buttons.append([InlineKeyboardButton(
            f"{icon} {name}", callback_data=cb
        )])

    buttons.append([InlineKeyboardButton("⬅️ Products", callback_data="admin_products")])
    await query.edit_message_text(
        "Select a product:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================================================
# CALLBACKS
# =========================================================

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ---------- Customer ----------
    if data == "home":
        await query.edit_message_text("🏠 Main Menu", reply_markup=main_menu())
        return

    if data == "all":
        await query.edit_message_text(
            "🛍️ <b>All Products</b>",
            parse_mode="HTML",
            reply_markup=await products_page()
        )
        return

    if data.startswith("cat_"):
        cat = data[4:]
        await query.edit_message_text(
            CATEGORIES.get(cat, "Products"),
            reply_markup=await products_page(cat)
        )
        return

    if data.startswith("product_"):
        await show_product(query, int(data.split("_")[1]))
        return

    if data.startswith("order_") and not data.startswith("order_view_"):
        pid = int(data.split("_")[1])
        con = db()
        row = con.execute(
            "SELECT name,active FROM products WHERE id=?", (pid,)
        ).fetchone()
        con.close()
        if not row or not row[1]:
            await query.answer("Product is unavailable.", show_alert=True)
            return
        await query.edit_message_text(
            f"🛒 <b>{row[0]}</b>\n\n💳 <b>Select payment method:</b>",
            parse_mode="HTML",
            reply_markup=payment_menu(pid)
        )
        return

    if data.startswith("pay_binance_") or data.startswith("pay_trc20_") or data.startswith("pay_bep20_"):
        if data.startswith("pay_binance_"):
            pid, method, key = int(data.split("_")[2]), "Binance", "binance"
        elif data.startswith("pay_trc20_"):
            pid, method, key = int(data.split("_")[2]), "USDT TRC20", "trc20"
        else:
            pid, method, key = int(data.split("_")[2]), "USDT BEP20", "bep20"

        con = db()
        row = con.execute(
            "SELECT name,price_info FROM products WHERE id=? AND active=1", (pid,)
        ).fetchone()
        if not row:
            con.close()
            await query.answer("Product unavailable.", show_alert=True)
            return

        cur = con.execute(
            """INSERT INTO orders(user_id,username,product_id,payment_method,status,created_at)
               VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (query.from_user.id, query.from_user.username or "", pid, method, "Payment Pending")
        )
        order_id = cur.lastrowid
        con.commit()
        con.close()

        context.user_data["pending_order_id"] = order_id
        context.user_data["pending_product_id"] = pid
        context.user_data["pending_payment_method"] = method

        if ADMIN_ID:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 <b>New Order #{order_id}</b>\n\n"
                f"👤 @{query.from_user.username or 'N/A'}\n"
                f"🆔 {query.from_user.id}\n"
                f"🛍️ {row[0]}\n"
                f"💰 {row[1]}\n"
                f"💳 {method}\n"
                f"⏳ Payment Pending",
                parse_mode="HTML"
            )

        await query.edit_message_text(
            f"✅ <b>Order #{order_id} Created</b>\n\n"
            f"🛍️ <b>Product:</b> {row[0]}\n"
            f"💰 <b>Price:</b> {row[1]}\n"
            f"💳 <b>Payment:</b> {method}\n\n"
            f"{payment_details(key)}",
            parse_mode="HTML",
            reply_markup=payment_proof_button()
        )
        return

    if data == "send_proof":
        if not context.user_data.get("pending_order_id"):
            await query.answer("No pending order found.", show_alert=True)
            return
        context.user_data["awaiting_proof"] = True
        await query.edit_message_text(
            "📤 <b>Send Payment Proof</b>\n\n"
            "Please send your payment screenshot as a photo.",
            parse_mode="HTML",
            reply_markup=back_home_keyboard()
        )
        return

    if data == "myorders":
        con = db()
        rows = con.execute("""
            SELECT o.id,p.name,o.payment_method,o.status
            FROM orders o JOIN products p ON p.id=o.product_id
            WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10
        """, (query.from_user.id,)).fetchall()
        con.close()
        text = "📦 <b>Your Orders</b>\n\n"
        text += "\n".join(
            f"#{oid} — {name} — {payment or 'N/A'} — {status}"
            for oid, name, payment, status in rows
        ) if rows else "No orders yet."
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_home_keyboard())
        return

    if data == "support":
        await query.edit_message_text(
            "💬 <b>Support</b>\n\nPlease contact our support/admin.",
            parse_mode="HTML", reply_markup=back_home_keyboard()
        )
        return

    # ---------- Admin ----------
    if data == "admin":
        if not await admin_only(update):
            return
        await query.edit_message_text(
            "⚙️ <b>ADMIN PANEL</b>\n\nChoose an option:",
            parse_mode="HTML", reply_markup=admin_menu()
        )
        return

    if data == "admin_products":
        if not await admin_only(update):
            return
        await admin_products_menu(query)
        return

    if data == "admin_payment":
        if not await admin_only(update):
            return
        await admin_payment_menu(query)
        return

    if data == "admin_orders":
        if not await admin_only(update):
            return
        await admin_orders_menu(query)
        return

    if data == "admin_stats":
        if not await admin_only(update):
            return
        await admin_stats(query)
        return

    if data == "admin_broadcast":
        if not await admin_only(update):
            return
        context.user_data["admin_action"] = "broadcast"
        await query.edit_message_text(
            "📢 <b>Broadcast</b>\n\nSend the message you want to broadcast to all users who have placed an order.",
            parse_mode="HTML"
        )
        return

    if data == "add_product":
        if not await admin_only(update):
            return
        context.user_data["admin_action"] = "add_name"
        context.user_data["new_product"] = {}
        await query.edit_message_text("➕ Send product name:")
        return

    if data == "edit_products":
        if not await admin_only(update):
            return
        await admin_product_list(query, "edit")
        return

    if data == "toggle_products":
        if not await admin_only(update):
            return
        await admin_product_list(query, "toggle")
        return

    if data == "delete_products":
        if not await admin_only(update):
            return
        await admin_product_list(query, "delete")
        return

    if data.startswith("edit_") and data[5:].isdigit():
        if not await admin_only(update):
            return
        pid = int(data[5:])
        con = db()
        row = con.execute(
            "SELECT name,category,price_info,warranty FROM products WHERE id=?", (pid,)
        ).fetchone()
        con.close()
        if not row:
            await query.answer("Product not found.", show_alert=True)
            return
        context.user_data["edit_pid"] = pid
        context.user_data["admin_action"] = "edit_name"
        await query.edit_message_text(
            f"✏️ Editing <b>{row[0]}</b>\n\n"
            "Send the new product name.\n"
            "Send /skip to keep the current name.",
            parse_mode="HTML"
        )
        return

    if data.startswith("toggle_") and data[7:].isdigit():
        if not await admin_only(update):
            return
        pid = int(data[7:])
        con = db()
        con.execute(
            "UPDATE products SET active=CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?",
            (pid,)
        )
        con.commit()
        con.close()
        await query.answer("Product status updated.")
        await admin_product_list(query, "toggle")
        return

    if data.startswith("delete_") and data[7:].isdigit():
        if not await admin_only(update):
            return
        pid = int(data[7:])
        context.user_data["delete_pid"] = pid
        await query.edit_message_text(
            "⚠️ Are you sure you want to delete this product?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{pid}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="delete_products")]
            ])
        )
        return

    if data.startswith("confirm_delete_") and data[15:].isdigit():
        if not await admin_only(update):
            return
        pid = int(data[15:])
        con = db()
        con.execute("DELETE FROM products WHERE id=?", (pid,))
        con.commit()
        con.close()
        await query.edit_message_text(
            "✅ Product deleted.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Products", callback_data="admin_products")]
            ])
        )
        return

    if data.startswith("set_"):
        if not await admin_only(update):
            return
        key = data[4:]
        if key not in ("binance_uid", "usdt_trc20", "usdt_bep20"):
            return
        context.user_data["admin_action"] = f"set_{key}"
        labels = {
            "binance_uid": "🟡 Send new Binance UID:",
            "usdt_trc20": "🔴 Send new USDT TRC20 address:",
            "usdt_bep20": "🟢 Send new USDT BEP20 address:",
        }
        await query.edit_message_text(labels[key])
        return

    if data.startswith("order_view_") and data[11:].isdigit():
        if not await admin_only(update):
            return
        oid = int(data[11:])
        con = db()
        row = con.execute("""
            SELECT o.id,o.user_id,o.username,p.name,o.payment_method,o.status,o.created_at
            FROM orders o LEFT JOIN products p ON p.id=o.product_id
            WHERE o.id=?
        """, (oid,)).fetchone()
        con.close()
        if not row:
            await query.answer("Order not found.", show_alert=True)
            return
        oid,user_id,username,pname,payment,status,created = row
        await query.edit_message_text(
            f"🧾 <b>Order #{oid}</b>\n\n"
            f"👤 @{username or 'N/A'}\n"
            f"🆔 {user_id}\n"
            f"🛍️ {pname or 'Deleted product'}\n"
            f"💳 {payment or 'N/A'}\n"
            f"⏳ {status}\n"
            f"🕐 {created or 'N/A'}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Mark Paid", callback_data=f"status_paid_{oid}")],
                [InlineKeyboardButton("📦 Mark Completed", callback_data=f"status_completed_{oid}")],
                [InlineKeyboardButton("❌ Cancel Order", callback_data=f"status_cancelled_{oid}")],
                [InlineKeyboardButton("⬅️ Orders", callback_data="admin_orders")]
            ])
        )
        return

    if data.startswith("status_") and "_" in data[7:]:
        if not await admin_only(update):
            return
        parts = data.split("_")
        status = parts[1].replace("paid", "Paid").replace("completed", "Completed").replace("cancelled", "Cancelled")
        oid = int(parts[2])
        con = db()
        con.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        row = con.execute("SELECT user_id FROM orders WHERE id=?", (oid,)).fetchone()
        con.commit()
        con.close()
        if row:
            messages = {
                "Paid": f"💰 Order #{oid} has been marked as paid.",
                "Completed": f"✅ Order #{oid} has been completed.",
                "Cancelled": f"❌ Order #{oid} has been cancelled."
            }
            try:
                await context.bot.send_message(row[0], messages.get(status, f"Order #{oid}: {status}"))
            except Exception:
                pass
        await query.answer("Order status updated.")
        await admin_orders_menu(query)
        return


# =========================================================
# ADMIN TEXT INPUT
# =========================================================

async def admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    action = context.user_data.get("admin_action")
    if not action:
        return

    text = update.message.text.strip()

    if text == "/skip" and action == "edit_name":
        pid = context.user_data["edit_pid"]
        con = db()
        row = con.execute(
            "SELECT name FROM products WHERE id=?", (pid,)
        ).fetchone()
        con.close()
        context.user_data["new_product"] = {"name": row[0]}
        context.user_data["admin_action"] = "edit_category"
        await update.message.reply_text(
            "Send category: ai / design / office / entertainment / software / other\n"
            "Or /skip to keep current category."
        )
        return

    if action.startswith("set_"):
        key = action[4:]
        set_setting(key, text)
        context.user_data.pop("admin_action", None)
        await update.message.reply_text(
            "✅ Payment setting updated.",
            reply_markup=admin_menu()
        )
        return

    if action == "add_name":
        context.user_data["new_product"]["name"] = text
        context.user_data["admin_action"] = "add_category"
        await update.message.reply_text(
            "Send category:\n"
            "ai / design / office / entertainment / software / other"
        )
        return

    if action == "add_category":
        if text not in CATEGORIES:
            await update.message.reply_text("❌ Invalid category. Try again.")
            return
        context.user_data["new_product"]["category"] = text
        context.user_data["admin_action"] = "add_price"
        await update.message.reply_text(
            "Send price information.\nExample:\n1 Month — $5\n1 Year — $20"
        )
        return

    if action == "add_price":
        context.user_data["new_product"]["price_info"] = text
        context.user_data["admin_action"] = "add_warranty"
        await update.message.reply_text(
            "Send warranty text, e.g. Full Warranty"
        )
        return

    if action == "add_warranty":
        p = context.user_data["new_product"]
        p["warranty"] = text
        con = db()
        con.execute(
            "INSERT INTO products(name,category,price_info,warranty,active) VALUES(?,?,?,?,1)",
            (p["name"], p["category"], p["price_info"], p["warranty"])
        )
        con.commit()
        con.close()
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Product added successfully.",
            reply_markup=admin_menu()
        )
        return

    if action == "edit_name":
        pid = context.user_data["edit_pid"]
        context.user_data["new_product"] = {"name": text}
        context.user_data["admin_action"] = "edit_category"
        await update.message.reply_text(
            "Send new category: ai / design / office / entertainment / software / other\n"
            "Or /skip to keep current category."
        )
        return

    if action == "edit_category":
        pid = context.user_data["edit_pid"]
        con = db()
        old = con.execute(
            "SELECT category,price_info,warranty FROM products WHERE id=?", (pid,)
        ).fetchone()
        con.close()
        if text == "/skip":
            category = old[0]
        else:
            if text not in CATEGORIES:
                await update.message.reply_text("❌ Invalid category.")
                return
            category = text
        context.user_data["new_product"]["category"] = category
        context.user_data["new_product"]["old_price"] = old[1]
        context.user_data["new_product"]["old_warranty"] = old[2]
        context.user_data["admin_action"] = "edit_price"
        await update.message.reply_text(
            f"Send new price information.\nCurrent:\n{old[1]}\n\n"
            "Or /skip to keep it."
        )
        return

    if action == "edit_price":
        pid = context.user_data["edit_pid"]
        p = context.user_data["new_product"]
        if text == "/skip":
            price = p["old_price"]
        else:
            price = text
        p["price_info"] = price
        context.user_data["admin_action"] = "edit_warranty"
        await update.message.reply_text(
            f"Send new warranty.\nCurrent:\n{p['old_warranty']}\n\n"
            "Or /skip to keep it."
        )
        return

    if action == "edit_warranty":
        pid = context.user_data["edit_pid"]
        p = context.user_data["new_product"]
        warranty = p["old_warranty"] if text == "/skip" else text
        con = db()
        con.execute(
            "UPDATE products SET name=?,category=?,price_info=?,warranty=? WHERE id=?",
            (p["name"], p["category"], p["price_info"], warranty, pid)
        )
        con.commit()
        con.close()
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Product updated.",
            reply_markup=admin_menu()
        )
        return

    if action == "broadcast":
        con = db()
        users = [r[0] for r in con.execute("SELECT DISTINCT user_id FROM orders").fetchall()]
        con.close()
        sent = 0
        for uid in users:
            try:
                await context.bot.send_message(uid, text)
                sent += 1
            except Exception:
                pass
        context.user_data.pop("admin_action", None)
        await update.message.reply_text(
            f"📢 Broadcast finished.\n\nSent: {sent}",
            reply_markup=admin_menu()
        )


# =========================================================
# PAYMENT PROOF
# =========================================================

async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return

    order_id = context.user_data.get("pending_order_id")
    awaiting = context.user_data.get("awaiting_proof")

    if not order_id or not awaiting:
        return

    pid = context.user_data.get("pending_product_id")
    payment = context.user_data.get("pending_payment_method", "N/A")

    con = db()
    row = con.execute(
        "SELECT name,price_info FROM products WHERE id=?", (pid,)
    ).fetchone()
    con.execute(
        "UPDATE orders SET status='Payment Proof Submitted' WHERE id=?",
        (order_id,)
    )
    con.commit()
    con.close()

    product_name = row[0] if row else "Unknown Product"
    price = row[1] if row else "N/A"
    username = update.effective_user.username or "N/A"
    user_id = update.effective_user.id

    if ADMIN_ID:
        await context.bot.send_photo(
            ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=(
                f"📸 <b>Payment Proof Received</b>\n\n"
                f"🧾 Order: #{order_id}\n"
                f"👤 @{username}\n"
                f"🆔 {user_id}\n"
                f"🛍️ {product_name}\n"
                f"💰 {price}\n"
                f"💳 {payment}\n"
                f"⏳ Payment Proof Submitted"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Open Orders", callback_data="admin_orders")]
            ])
        )

    await update.message.reply_text(
        f"✅ <b>Payment proof received!</b>\n\n"
        f"🧾 Order #{order_id}\n"
        "Our admin will verify your payment and process the order.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

    context.user_data.clear()


# =========================================================
# MAIN
# =========================================================

def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Set BOT_TOKEN environment variable first.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    # Admin text actions must be before generic photo handling.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_input))
    app.add_handler(MessageHandler(filters.PHOTO, receive_payment_proof))

    app.add_handler(CallbackQueryHandler(callback))

    app.run_polling()


if __name__ == "__main__":
    main()
