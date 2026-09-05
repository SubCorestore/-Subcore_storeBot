import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = "shop.db"

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

def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price_info TEXT NOT NULL,
        warranty TEXT DEFAULT 'Full Warranty',
        photo_id TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        product_id INTEGER,
        status TEXT DEFAULT 'New'
    )""")
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO products(name,category,price_info,warranty) VALUES(?,?,?,?)",
            DEFAULT_PRODUCTS
        )
    con.commit()
    return con

db()

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ All Products", callback_data="all")],
        [InlineKeyboardButton("🤖 AI Tools", callback_data="cat_ai"),
         InlineKeyboardButton("🎨 Design & Video", callback_data="cat_design")],
        [InlineKeyboardButton("💼 Office & Productivity", callback_data="cat_office"),
         InlineKeyboardButton("📺 Entertainment", callback_data="cat_entertainment")],
        [InlineKeyboardButton("🛠️ Software", callback_data="cat_software"),
         InlineKeyboardButton("📦 Other Products", callback_data="cat_other")],
        [InlineKeyboardButton("📦 My Orders", callback_data="myorders"),
         InlineKeyboardButton("💬 Support", callback_data="support")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "✨ Welcome to Our Digital Store ✨\n\n"
        "🛡️ Full Warranty Included\n"
        "⚡ Stable Access\n"
        "🚀 Fast Delivery & Dedicated Support\n\n"
        "Choose a category below:"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

async def products_page(query, category=None):
    con = db()
    if category:
        rows = con.execute(
            "SELECT id,name FROM products WHERE category=? ORDER BY id DESC", (category,)
        ).fetchall()
    else:
        rows = con.execute("SELECT id,name FROM products ORDER BY id DESC").fetchall()
    con.close()

    buttons = [[InlineKeyboardButton(name, callback_data=f"product_{pid}")] for pid, name in rows]
    buttons.append([InlineKeyboardButton("⬅️ Main Menu", callback_data="home")])
    return InlineKeyboardMarkup(buttons)

async def show_product(query, pid):
    con = db()
    row = con.execute(
        "SELECT id,name,price_info,warranty,photo_id FROM products WHERE id=?", (pid,)
    ).fetchone()
    con.close()
    if not row:
        await query.answer("Product not found.", show_alert=True)
        return
    _, name, price_info, warranty, photo_id = row
    text = f"🛍️ <b>{name}</b>\n\n💰 {price_info}\n\n🛡️ Warranty: {warranty}\n⚡ Fast Delivery & Support"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Order Now", callback_data=f"order_{pid}")],
        [InlineKeyboardButton("⬅️ Products", callback_data="all")],
    ])
    if photo_id:
        await query.message.reply_photo(photo_id, caption=text, parse_mode="HTML", reply_markup=kb)
        try:
            await query.message.delete()
        except Exception:
            pass
    else:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "home":
        await query.edit_message_text("🏠 Main Menu", reply_markup=main_menu())
    elif data == "all":
        await query.edit_message_text("🛍️ All Products:", reply_markup=await products_page(query))
    elif data.startswith("cat_"):
        cat = data[4:]
        await query.edit_message_text(CATEGORIES.get(cat, "Products"), reply_markup=await products_page(query, cat))
    elif data.startswith("product_"):
        await show_product(query, int(data.split("_")[1]))
    elif data.startswith("order_"):
        pid = int(data.split("_")[1])
        con = db()
        row = con.execute("SELECT name FROM products WHERE id=?", (pid,)).fetchone()
        if not row:
            con.close()
            await query.answer("Product not found.", show_alert=True)
            return
        con.execute(
            "INSERT INTO orders(user_id,username,product_id) VALUES(?,?,?)",
            (query.from_user.id, query.from_user.username or "", pid)
        )
        order_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.commit()
        con.close()

        if ADMIN_ID:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 New Order #{order_id}\n\n"
                f"👤 User: @{query.from_user.username or 'N/A'}\n"
                f"🆔 ID: {query.from_user.id}\n"
                f"🛍️ Product: {row[0]}\n\n"
                f"Please process the order manually."
            )
        await query.edit_message_text(
            f"✅ Order #{order_id} received!\n\n"
            f"🛍️ {row[0]}\n\n"
            f"💬 Please contact support/payment instructions to complete your order.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="home")]])
        )
    elif data == "support":
        await query.edit_message_text(
            "💬 Support\n\nPlease contact our support/admin to complete your order.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="home")]])
        )
    elif data == "myorders":
        con = db()
        rows = con.execute("""
            SELECT o.id,p.name,o.status FROM orders o
            JOIN products p ON p.id=o.product_id
            WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10
        """, (query.from_user.id,)).fetchall()
        con.close()
        text = "📦 Your Orders\n\n" + (
            "\n".join(f"#{oid} — {name} — {status}" for oid,name,status in rows)
            if rows else "No orders yet."
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="home")]]))

# -------- Admin: add product with photo --------
ADD_NAME, ADD_CATEGORY, ADD_PRICE, ADD_WARRANTY, ADD_PHOTO = range(5)

def is_admin(update):
    return ADMIN_ID and update.effective_user and update.effective_user.id == ADMIN_ID

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Admin only.")
        return ConversationHandler.END
    await update.message.reply_text("Send the new product name:")
    return ADD_NAME

async def add_name(update, context):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("Send category: ai / design / office / entertainment / software / other")
    return ADD_CATEGORY

async def add_category(update, context):
    cat = update.message.text.strip().lower()
    if cat not in CATEGORIES:
        await update.message.reply_text("Invalid category. Use: ai, design, office, entertainment, software, other")
        return ADD_CATEGORY
    context.user_data["category"] = cat
    await update.message.reply_text("Send price/duration information, e.g.:\n1 Month — $5\n1 Year — $20")
    return ADD_PRICE

async def add_price(update, context):
    context.user_data["price"] = update.message.text.strip()
    await update.message.reply_text("Send warranty type (e.g. Full Warranty / No Warranty):")
    return ADD_WARRANTY

async def add_warranty(update, context):
    context.user_data["warranty"] = update.message.text.strip()
    await update.message.reply_text("Now send the product photo. You can also send /skip_photo")
    return ADD_PHOTO

async def add_photo(update, context):
    photo_id = update.message.photo[-1].file_id
    save_product(context, photo_id)
    await update.message.reply_text("✅ Product added successfully!")
    context.user_data.clear()
    return ConversationHandler.END

async def skip_photo(update, context):
    save_product(context, None)
    await update.message.reply_text("✅ Product added without a photo.")
    context.user_data.clear()
    return ConversationHandler.END

def save_product(context, photo_id):
    con = db()
    con.execute(
        "INSERT INTO products(name,category,price_info,warranty,photo_id) VALUES(?,?,?,?,?)",
        (context.user_data["name"], context.user_data["category"],
         context.user_data["price"], context.user_data["warranty"], photo_id)
    )
    con.commit()
    con.close()

async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

async def admin_products(update, context):
    if not is_admin(update):
        return
    con = db()
    rows = con.execute("SELECT id,name FROM products ORDER BY id DESC").fetchall()
    con.close()
    text = "🛠️ Products:\n\n" + "\n".join(f"{pid}. {name}" for pid,name in rows)
    await update.message.reply_text(text)

def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Set BOT_TOKEN environment variable first.")
    app = Application.builder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_category)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_WARRANTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_warranty)],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, add_photo),
                CommandHandler("skip_photo", skip_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", admin_products))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(callback))
    app.run_polling()

if __name__ == "__main__":
    main()
