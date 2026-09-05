import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ============================================================
# BASIC SETTINGS
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
DB = "shop.db"

# Your payment information
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
    ("CapCut Pro Personal", "design", "1 Month — $3.5\n6 Months — $12\n1 Year — $20\nCustomer Email — $20\nMonthly Renewal available", "Full Warranty"),
    ("ChatGPT Plus Personal", "ai", "Customer Email — 1 Month — $18", "Full Warranty"),
    ("ChatGPT Shared", "ai", "1 Month — $3.5", "Full Warranty"),
    ("Gemini Pro + Google Drive 5TB", "ai", "1 Month — $1\n12 Months — $3.5\nFamily Plan (5 Invites) — 12 Months — $8", "Full Warranty"),
    ("YouTube Premium", "entertainment", "1 Month — $1\n12 Months — $10\nMonthly Renewal available", "Full Warranty"),
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


# ============================================================
# RENDER WEB-SERVICE HEALTH SERVER
# This prevents Render Web Service port timeout.
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Telegram Store Bot is running.")

    def log_message(self, format, *args):
        pass


def start_web_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# ============================================================
# DATABASE
# ============================================================

def get_db():
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
            status TEXT DEFAULT 'New',
            txid TEXT DEFAULT ''
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Safe migration for an older shop.db created by the previous bot.
    product_columns = {
        row[1] for row in con.execute("PRAGMA table_info(products)").fetchall()
    }
    if "active" not in product_columns:
        con.execute("ALTER TABLE products ADD COLUMN active INTEGER DEFAULT 1")

    order_columns = {
        row[1] for row in con.execute("PRAGMA table_info(orders)").fetchall()
    }
    if "txid" not in order_columns:
        con.execute("ALTER TABLE orders ADD COLUMN txid TEXT DEFAULT ''")

    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO products(name,category,price_info,warranty) VALUES(?,?,?,?)",
            DEFAULT_PRODUCTS,
        )

    defaults = {
        "binance_uid": DEFAULT_PAYMENT["binance_uid"],
        "usdt_trc20": DEFAULT_PAYMENT["usdt_trc20"],
        "usdt_bep20": DEFAULT_PAYMENT["usdt_bep20"],
        "support_text": "💬 Please contact admin/support for help.",
    }
    for key, value in defaults.items():
        con.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value),
        )

    con.commit()
    return con


def setting(key):
    con = get_db()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row[0] if row else ""


def set_setting(key, value):
    con = get_db()
    con.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    con.commit()
    con.close()


get_db()


# ============================================================
# COMMON UI
# ============================================================

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ All Products", callback_data="all")],
        [
            InlineKeyboardButton("🤖 AI Tools", callback_data="cat_ai"),
            InlineKeyboardButton("🎨 Design & Video", callback_data="cat_design"),
        ],
        [
            InlineKeyboardButton("💼 Office & Productivity", callback_data="cat_office"),
            InlineKeyboardButton("📺 Entertainment", callback_data="cat_entertainment"),
        ],
        [
            InlineKeyboardButton("🛠️ Software", callback_data="cat_software"),
            InlineKeyboardButton("📦 Other Products", callback_data="cat_other"),
        ],
        [
            InlineKeyboardButton("📦 My Orders", callback_data="myorders"),
            InlineKeyboardButton("💬 Support", callback_data="support"),
        ],
    ])


def back_home():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")]
    ])


def is_admin(update):
    return bool(
        ADMIN_ID
        and update.effective_user
        and update.effective_user.id == ADMIN_ID
    )


async def deny_admin(update):
    if update.callback_query:
        await update.callback_query.answer("⛔ Admin only.", show_alert=True)
    elif update.message:
        await update.message.reply_text("⛔ Admin only.")


# ============================================================
# CUSTOMER SIDE
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "✨ <b>Welcome to Our Digital Store</b> ✨\n\n"
        "🛡️ Full Warranty Included\n"
        "⚡ Stable Access\n"
        "🚀 Fast Delivery & Dedicated Support\n\n"
        "Choose a category below:"
    )
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=main_menu()
    )


async def products_keyboard(category=None):
    con = get_db()
    if category:
        rows = con.execute(
            "SELECT id,name FROM products "
            "WHERE category=? AND active=1 ORDER BY id DESC",
            (category,),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id,name FROM products WHERE active=1 ORDER BY id DESC"
        ).fetchall()
    con.close()

    buttons = [
        [InlineKeyboardButton(name, callback_data=f"product_{pid}")]
        for pid, name in rows
    ]
    buttons.append([InlineKeyboardButton("⬅️ Main Menu", callback_data="home")])
    return InlineKeyboardMarkup(buttons)


async def show_product(query, pid):
    con = get_db()
    row = con.execute(
        "SELECT id,name,price_info,warranty,photo_id FROM products "
        "WHERE id=? AND active=1",
        (pid,),
    ).fetchone()
    con.close()

    if not row:
        await query.answer("Product not found.", show_alert=True)
        return

    _, name, price_info, warranty, photo_id = row
    text = (
        f"🛍️ <b>{escape(name)}</b>\n\n"
        f"💰 {escape(price_info)}\n\n"
        f"🛡️ Warranty: {escape(warranty)}\n"
        "⚡ Fast Delivery & Support"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Order Now", callback_data=f"order_{pid}")],
        [InlineKeyboardButton("⬅️ Products", callback_data="all")],
    ])

    if photo_id:
        try:
            await query.message.reply_photo(
                photo_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb,
            )
            try:
                await query.message.delete()
            except Exception:
                pass
        except Exception:
            await query.edit_message_text(
                text, parse_mode="HTML", reply_markup=kb
            )
    else:
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=kb
        )


def payment_text():
    return (
        "💳 <b>Payment Information</b>\n\n"
        f"Binance UID: <code>{escape(setting('binance_uid'))}</code>\n\n"
        f"USDT TRC20:\n<code>{escape(setting('usdt_trc20'))}</code>\n\n"
        f"USDT BEP20:\n<code>{escape(setting('usdt_bep20'))}</code>\n\n"
        "After payment, tap <b>I Have Paid</b> and send your transaction ID."
    )


async def create_order(query, context, pid):
    con = get_db()
    row = con.execute(
        "SELECT name,price_info FROM products WHERE id=? AND active=1",
        (pid,),
    ).fetchone()

    if not row:
        con.close()
        await query.answer("Product not found.", show_alert=True)
        return

    name, price_info = row
    con.execute(
        "INSERT INTO orders(user_id,username,product_id) VALUES(?,?,?)",
        (query.from_user.id, query.from_user.username or "", pid),
    )
    order_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()

    if ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 <b>New Order #{order_id}</b>\n\n"
                f"👤 User: @{escape(query.from_user.username or 'N/A')}\n"
                f"🆔 ID: <code>{query.from_user.id}</code>\n"
                f"🛍️ Product: {escape(name)}\n"
                f"💰 {escape(price_info)}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Payment Info", callback_data=f"pay_{order_id}")],
        [InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_{order_id}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="home")],
    ])

    await query.edit_message_text(
        f"✅ <b>Order #{order_id} created!</b>\n\n"
        f"🛍️ {escape(name)}\n"
        f"💰 {escape(price_info)}\n\n"
        "Please complete payment and then submit your transaction ID.",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ============================================================
# PAID / TXID FLOW
# ============================================================

async def ask_txid(query, context, order_id):
    context.user_data["waiting_txid_order"] = order_id
    await query.edit_message_text(
        f"🧾 <b>Order #{order_id}</b>\n\n"
        "Send your Binance/USDT transaction ID (TXID) here.\n\n"
        "If you have not paid yet, use /cancel.",
        parse_mode="HTML",
    )


async def receive_txid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("waiting_txid_order")
    if not order_id:
        return False

    txid = update.message.text.strip()
    if len(txid) < 5:
        await update.message.reply_text("Please send a valid transaction ID.")
        return True

    con = get_db()
    row = con.execute(
        "SELECT o.id,o.user_id,o.username,p.name "
        "FROM orders o JOIN products p ON p.id=o.product_id "
        "WHERE o.id=? AND o.user_id=?",
        (order_id, update.effective_user.id),
    ).fetchone()

    if not row:
        con.close()
        context.user_data.pop("waiting_txid_order", None)
        await update.message.reply_text("Order not found.")
        return True

    con.execute(
        "UPDATE orders SET txid=?,status='Payment Submitted' WHERE id=?",
        (txid, order_id),
    )
    con.commit()
    con.close()

    context.user_data.pop("waiting_txid_order", None)

    if ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"💰 <b>Payment Submitted — Order #{order_id}</b>\n\n"
                f"👤 @{escape(row[2] or 'N/A')}\n"
                f"🆔 <code>{row[1]}</code>\n"
                f"🛍️ {escape(row[3])}\n"
                f"🧾 TXID: <code>{escape(txid)}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ Mark Completed",
                            callback_data=f"complete_{order_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "❌ Cancel Order",
                            callback_data=f"cancelorder_{order_id}",
                        )
                    ],
                ]),
            )
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ Payment information received for Order #{order_id}.\n\n"
        "Admin will verify your payment and process the order.",
        reply_markup=back_home(),
    )
    return True


# ============================================================
# MY ORDERS / CUSTOMER CALLBACK
# ============================================================

async def customer_callback(query, context, data):
    if data == "home":
        await query.edit_message_text("🏠 Main Menu", reply_markup=main_menu())
        return

    if data == "all":
        await query.edit_message_text(
            "🛍️ <b>All Products:</b>",
            parse_mode="HTML",
            reply_markup=await products_keyboard(),
        )
        return

    if data.startswith("cat_"):
        cat = data[4:]
        await query.edit_message_text(
            CATEGORIES.get(cat, "Products"),
            reply_markup=await products_keyboard(cat),
        )
        return

    if data.startswith("product_"):
        await show_product(query, int(data.split("_")[1]))
        return

    if data.startswith("order_"):
        await create_order(query, context, int(data.split("_")[1]))
        return

    if data.startswith("pay_"):
        order_id = int(data.split("_")[1])
        await query.edit_message_text(
            f"💳 <b>Order #{order_id}</b>\n\n" + payment_text(),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "✅ I Have Paid",
                    callback_data=f"paid_{order_id}",
                )],
                [InlineKeyboardButton(
                    "🏠 Main Menu",
                    callback_data="home",
                )],
            ]),
        )
        return

    if data.startswith("paid_"):
        await ask_txid(query, context, int(data.split("_")[1]))
        return

    if data == "support":
        await query.edit_message_text(
            setting("support_text"),
            reply_markup=back_home(),
        )
        return

    if data == "myorders":
        con = get_db()
        rows = con.execute(
            "SELECT o.id,p.name,o.status "
            "FROM orders o JOIN products p ON p.id=o.product_id "
            "WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10",
            (query.from_user.id,),
        ).fetchall()
        con.close()

        text = "📦 <b>Your Orders</b>\n\n"
        text += (
            "\n".join(
                f"#{oid} — {escape(name)} — {escape(status)}"
                for oid, name, status in rows
            )
            if rows else "No orders yet."
        )
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=back_home()
        )


# ============================================================
# ADMIN PANEL
# ============================================================

def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Products", callback_data="adm_products"),
            InlineKeyboardButton("💳 Payment", callback_data="adm_payment"),
        ],
        [
            InlineKeyboardButton("🛒 Orders", callback_data="adm_orders"),
            InlineKeyboardButton("📊 Stats", callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
            InlineKeyboardButton("⚙️ Support Text", callback_data="adm_support"),
        ],
    ])


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin(update)
        return
    await update.message.reply_text(
        "⚙️ <b>Admin Panel</b>\n\nChoose what you want to manage:",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


async def admin_products_page(query):
    con = get_db()
    rows = con.execute(
        "SELECT id,name,active FROM products ORDER BY id DESC"
    ).fetchall()
    con.close()

    buttons = []
    for pid, name, active in rows:
        icon = "🟢" if active else "🔴"
        buttons.append([
            InlineKeyboardButton(
                f"{icon} {name}",
                callback_data=f"admp_{pid}",
            )
        ])

    buttons.append([
        InlineKeyboardButton("➕ Add Product", callback_data="adm_add")
    ])
    buttons.append([
        InlineKeyboardButton("⬅️ Admin Panel", callback_data="adm_home")
    ])
    return InlineKeyboardMarkup(buttons)


async def admin_product_detail(query, pid):
    con = get_db()
    row = con.execute(
        "SELECT id,name,category,price_info,warranty,active "
        "FROM products WHERE id=?",
        (pid,),
    ).fetchone()
    con.close()

    if not row:
        await query.answer("Product not found.", show_alert=True)
        return

    _, name, category, price_info, warranty, active = row
    status = "🟢 Active" if active else "🔴 Disabled"

    text = (
        f"📦 <b>{escape(name)}</b>\n\n"
        f"Category: {escape(CATEGORIES.get(category, category))}\n"
        f"Status: {status}\n\n"
        f"💰 <b>Price:</b>\n{escape(price_info)}\n\n"
        f"🛡️ Warranty: {escape(warranty)}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Edit", callback_data=f"editp_{pid}"),
            InlineKeyboardButton(
                "🔴 Disable" if active else "🟢 Enable",
                callback_data=f"togglep_{pid}",
            ),
        ],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"delp_{pid}")],
        [InlineKeyboardButton("⬅️ Products", callback_data="adm_products")],
    ])

    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=kb
    )


# Product edit conversation
EP_NAME, EP_CATEGORY, EP_PRICE, EP_WARRANTY = range(10, 14)
ADD_NAME, ADD_CATEGORY, ADD_PRICE, ADD_WARRANTY = range(20, 24)


async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin(update)
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "➕ <b>Add Product</b>\n\nSend product name:",
        parse_mode="HTML",
    )
    return ADD_NAME


async def add_product_name(update, context):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "Send category:\n\nai / design / office / entertainment / software / other"
    )
    return ADD_CATEGORY


async def add_product_category(update, context):
    cat = update.message.text.strip().lower()
    if cat not in CATEGORIES:
        await update.message.reply_text(
            "❌ Invalid category.\nUse: ai / design / office / entertainment / software / other"
        )
        return ADD_CATEGORY
    context.user_data["category"] = cat
    await update.message.reply_text(
        "Send price/duration exactly how you want customers to see it.\n\n"
        "Example:\n1 Month — $5\n1 Year — $20"
    )
    return ADD_PRICE


async def add_product_price(update, context):
    context.user_data["price_info"] = update.message.text.strip()
    await update.message.reply_text(
        "Send warranty text.\nExample: Full Warranty"
    )
    return ADD_WARRANTY


async def add_product_warranty(update, context):
    context.user_data["warranty"] = update.message.text.strip()

    con = get_db()
    con.execute(
        "INSERT INTO products(name,category,price_info,warranty) VALUES(?,?,?,?)",
        (
            context.user_data["name"],
            context.user_data["category"],
            context.user_data["price_info"],
            context.user_data["warranty"],
        ),
    )
    con.commit()
    con.close()
    context.user_data.clear()

    await update.message.reply_text(
        "✅ Product added successfully!\n\nUse /admin to manage it."
    )
    return ConversationHandler.END


async def edit_product_start(query, context, pid):
    con = get_db()
    row = con.execute(
        "SELECT name,category,price_info,warranty FROM products WHERE id=?",
        (pid,),
    ).fetchone()
    con.close()

    if not row:
        await query.answer("Product not found.", show_alert=True)
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["edit_pid"] = pid
    context.user_data["name"] = row[0]
    context.user_data["category"] = row[1]
    context.user_data["price_info"] = row[2]
    context.user_data["warranty"] = row[3]

    await query.message.reply_text(
        f"✏️ Editing product #{pid}\n\n"
        f"Current name: {row[0]}\n\n"
        "Send the new product name."
    )
    return EP_NAME


async def edit_product_name(update, context):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "Send category:\nai / design / office / entertainment / software / other"
    )
    return EP_CATEGORY


async def edit_product_category(update, context):
    cat = update.message.text.strip().lower()
    if cat not in CATEGORIES:
        await update.message.reply_text("Invalid category. Try again.")
        return EP_CATEGORY
    context.user_data["category"] = cat
    await update.message.reply_text("Send new price/duration information.")
    return EP_PRICE


async def edit_product_price(update, context):
    context.user_data["price_info"] = update.message.text.strip()
    await update.message.reply_text("Send new warranty text.")
    return EP_WARRANTY


async def edit_product_warranty(update, context):
    context.user_data["warranty"] = update.message.text.strip()
    pid = context.user_data["edit_pid"]

    con = get_db()
    con.execute(
        "UPDATE products SET name=?,category=?,price_info=?,warranty=? WHERE id=?",
        (
            context.user_data["name"],
            context.user_data["category"],
            context.user_data["price_info"],
            context.user_data["warranty"],
            pid,
        ),
    )
    con.commit()
    con.close()
    context.user_data.clear()

    await update.message.reply_text(
        "✅ Product updated successfully!\n\nUse /admin to continue."
    )
    return ConversationHandler.END


# Payment edit conversation
PAY_UID, PAY_TRC20, PAY_BEP20 = range(30, 33)


async def payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "💳 <b>Payment Settings</b>\n\n"
        f"Current Binance UID: <code>{escape(setting('binance_uid'))}</code>\n\n"
        "Send new Binance UID:",
        parse_mode="HTML",
    )
    return PAY_UID


async def payment_uid(update, context):
    set_setting("binance_uid", update.message.text.strip())
    await update.message.reply_text("Send new USDT TRC20 address:")
    return PAY_TRC20


async def payment_trc20(update, context):
    set_setting("usdt_trc20", update.message.text.strip())
    await update.message.reply_text("Send new USDT BEP20 address:")
    return PAY_BEP20


async def payment_bep20(update, context):
    set_setting("usdt_bep20", update.message.text.strip())
    await update.message.reply_text(
        "✅ Payment information updated successfully!"
    )
    return ConversationHandler.END


async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "Send the new support message that customers should see."
    )
    return 40


async def support_save(update, context):
    set_setting("support_text", update.message.text.strip())
    await update.message.reply_text("✅ Support text updated.")
    return ConversationHandler.END


# Broadcast
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "📢 Send the message you want to broadcast to all users."
    )
    return 50


async def broadcast_send(update, context):
    text = update.message.text
    con = get_db()
    users = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT user_id FROM orders WHERE user_id IS NOT NULL"
        ).fetchall()
    ]
    con.close()

    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, text)
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(
        f"📢 Broadcast finished.\nSent to {sent} users."
    )
    return ConversationHandler.END


async def cancel_conversation(update, context):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def admin_callback(query, context, data):
    if not is_admin(query):
        await query.answer("⛔ Admin only.", show_alert=True)
        return

    if data == "adm_home":
        await query.edit_message_text(
            "⚙️ <b>Admin Panel</b>",
            parse_mode="HTML",
            reply_markup=admin_menu(),
        )
        return

    if data == "adm_products":
        await query.edit_message_text(
            "📦 <b>Products Manager</b>\n\n"
            "🟢 Active  🔴 Disabled",
            parse_mode="HTML",
            reply_markup=await admin_products_page(query),
        )
        return

    if data.startswith("admp_"):
        await admin_product_detail(query, int(data.split("_")[1]))
        return

    if data == "adm_payment":
        text = (
            "💳 <b>Payment Settings</b>\n\n"
            f"Binance UID:\n<code>{escape(setting('binance_uid'))}</code>\n\n"
            f"USDT TRC20:\n<code>{escape(setting('usdt_trc20'))}</code>\n\n"
            f"USDT BEP20:\n<code>{escape(setting('usdt_bep20'))}</code>"
        )
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Change Payment Info", callback_data="start_payment")],
                [InlineKeyboardButton("⬅️ Admin Panel", callback_data="adm_home")],
            ]),
        )
        return

    if data == "start_payment":
        await query.message.reply_text(
            "Use /payment to change Binance UID, TRC20 and BEP20."
        )
        return

    if data == "adm_orders":
        con = get_db()
        rows = con.execute(
            "SELECT o.id,p.name,o.status,o.username,o.txid "
            "FROM orders o JOIN products p ON p.id=o.product_id "
            "ORDER BY o.id DESC LIMIT 20"
        ).fetchall()
        con.close()

        if not rows:
            text = "🛒 No orders yet."
        else:
            text = "🛒 <b>Recent Orders</b>\n\n" + "\n".join(
                f"#{oid} — {escape(name)} — {escape(status)}"
                for oid, name, status, username, txid in rows
            )

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Panel", callback_data="adm_home")]
            ]),
        )
        return

    if data == "adm_stats":
        con = get_db()
        products = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        active = con.execute(
            "SELECT COUNT(*) FROM products WHERE active=1"
        ).fetchone()[0]
        orders = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        pending = con.execute(
            "SELECT COUNT(*) FROM orders WHERE status NOT IN ('Completed','Cancelled')"
        ).fetchone()[0]
        users = con.execute(
            "SELECT COUNT(DISTINCT user_id) FROM orders"
        ).fetchone()[0]
        con.close()

        text = (
            "📊 <b>Store Statistics</b>\n\n"
            f"👥 Customers: {users}\n"
            f"📦 Products: {products}\n"
            f"🟢 Active Products: {active}\n"
            f"🛒 Total Orders: {orders}\n"
            f"⏳ Pending Orders: {pending}"
        )
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Panel", callback_data="adm_home")]
            ]),
        )
        return

    if data == "adm_broadcast":
        await query.message.reply_text(
            "Use /broadcast to send a message to customers."
        )
        return

    if data == "adm_support":
        await query.message.reply_text(
            "Use /supporttext to change the customer support message."
        )
        return

    if data == "adm_add":
        await query.message.reply_text(
            "Use /addproduct to add a new product."
        )
        return

    if data.startswith("togglep_"):
        pid = int(data.split("_")[1])
        con = get_db()
        con.execute(
            "UPDATE products SET active=CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?",
            (pid,),
        )
        con.commit()
        con.close()
        await admin_product_detail(query, pid)
        return

    if data.startswith("delp_"):
        pid = int(data.split("_")[1])
        con = get_db()
        con.execute("DELETE FROM products WHERE id=?", (pid,))
        con.commit()
        con.close()
        await query.edit_message_text(
            "🗑️ Product deleted.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Products", callback_data="adm_products")]
            ]),
        )
        return

    if data.startswith("editp_"):
        pid = int(data.split("_")[1])
        # Telegram callback cannot start a ConversationHandler state directly.
        # Send the admin to the command with the product ID.
        await query.message.reply_text(
            f"To edit product #{pid}, send:\n\n/editproduct {pid}"
        )
        return

    if data.startswith("complete_") or data.startswith("cancelorder_"):
        oid = int(data.split("_")[1])
        status = "Completed" if data.startswith("complete_") else "Cancelled"

        con = get_db()
        row = con.execute(
            "SELECT user_id FROM orders WHERE id=?", (oid,)
        ).fetchone()
        con.execute(
            "UPDATE orders SET status=? WHERE id=?", (status, oid)
        )
        con.commit()
        con.close()

        if row:
            try:
                await context.bot.send_message(
                    row[0],
                    f"📦 Order #{oid} status updated: {status}",
                )
            except Exception:
                pass

        await query.edit_message_text(
            f"✅ Order #{oid} marked as <b>{status}</b>.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Admin Panel", callback_data="adm_home")]
            ]),
        )
        return


# ============================================================
# EDIT PRODUCT COMMAND
# ============================================================

async def edit_product_command(update, context):
    if not is_admin(update):
        await deny_admin(update)
        return ConversationHandler.END

    if not context.args:
        await update.message.reply_text(
            "Usage: /editproduct PRODUCT_ID\nExample: /editproduct 1"
        )
        return ConversationHandler.END

    try:
        pid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Product ID must be a number.")
        return ConversationHandler.END

    con = get_db()
    row = con.execute(
        "SELECT name,category,price_info,warranty FROM products WHERE id=?",
        (pid,),
    ).fetchone()
    con.close()

    if not row:
        await update.message.reply_text("Product not found.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["edit_pid"] = pid
    await update.message.reply_text(
        f"✏️ Editing #{pid}\n\n"
        f"Current name: {row[0]}\n\n"
        "Send the new product name:"
    )
    return EP_NAME


# ============================================================
# MAIN CALLBACK ROUTER
# ============================================================

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith(("adm_", "admp_", "editp_", "togglep_", "delp_", "complete_", "cancelorder_", "start_payment")):
        await admin_callback(query, context, data)
        return

    await customer_callback(query, context, data)


# ============================================================
# START
# ============================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing. "
            "Add your Telegram bot token in Render Environment Variables."
        )

    # Start HTTP health server for Render Web Service.
    threading.Thread(target=start_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # Customer
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    # Simple admin commands
    # Conversations and admin commands
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("addproduct", add_product_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            ADD_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_category)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
            ADD_WARRANTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_warranty)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True,
    )
    app.add_handler(add_conv)

    # Payment conversation
    pay_conv = ConversationHandler(
        entry_points=[CommandHandler("payment", payment_start)],
        states={
            PAY_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_uid)],
            PAY_TRC20: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_trc20)],
            PAY_BEP20: [MessageHandler(filters.TEXT & ~filters.COMMAND, payment_bep20)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True,
    )
    app.add_handler(pay_conv)

    # Broadcast conversation
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            50: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True,
    )
    app.add_handler(broadcast_conv)

    # Support text conversation
    support_conv = ConversationHandler(
        entry_points=[CommandHandler("supporttext", support_start)],
        states={
            40: [MessageHandler(filters.TEXT & ~filters.COMMAND, support_save)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        allow_reentry=True,
    )
    app.add_handler(support_conv)

    # Customer TXID handler — only catches messages when waiting for TXID.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_txid),
        group=1,
    )

    app.add_handler(CallbackQueryHandler(callback_router))

    print("Bot started successfully.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
