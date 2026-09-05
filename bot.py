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

# =========================
# PAYMENT INFORMATION
# =========================

BINANCE_UID = "551481540"
USDT_TRC20 = "TQYfgwzEN8DFNE7LKPeppgSps2bcR5awFw"
USDT_BEP20 = "0xc1af1a00dca6c8012e4f88a4934dbf3a28a1102a"

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

    ("ChatGPT Plus Personal", "ai",
     "Customer Email — 1 Month — $18",
     "Full Warranty"),

    ("ChatGPT Shared", "ai",
     "1 Month — $3.5",
     "Full Warranty"),

    ("Gemini Pro + Google Drive 5TB", "ai",
     "1 Month — $1\n12 Months — $3.5\nFamily Plan (5 Invites) — 12 Months — $8",
     "Full Warranty"),

    ("YouTube Premium", "entertainment",
     "1 Month — $1\n12 Months — $10\nMonthly Renewal available",
     "Full Warranty"),

    ("Amazon Prime", "entertainment",
     "1 Month — $2\n6 Months — $4",
     "Full Warranty"),

    ("Zoom Pro (100 Participants)", "office",
     "1 Month — $2.5",
     "Full Warranty"),

    ("Canva Pro", "design",
     "1 Month — $1\n12 Months — $7\nMonthly Renewal available",
     "Full Warranty"),

    ("Netflix Full Account", "entertainment",
     "1 Month — $7",
     "Full Warranty"),

    ("Claude Pro", "ai",
     "1 Month — $20",
     "Full Warranty"),

    ("Lovable Lite Personal", "ai",
     "12 Months — $15",
     "Full Warranty"),

    ("AutoCAD", "software",
     "1 Year — $6",
     "Full Warranty"),

    ("Microsoft Office 365 Readymade", "office",
     "1 Year — $6.4",
     "Full Warranty"),

    ("Microsoft Office 365 Personal Gmail", "office",
     "1 Year — $12",
     "Full Warranty"),

    ("Wondershare Recoverit", "software",
     "1 Year — $5",
     "Full Warranty"),

    ("Wondershare Filmora", "design",
     "1 Year — $3",
     "Full Warranty"),
]


# =========================
# DATABASE
# =========================

def db():
    con = sqlite3.connect(DB)

    con.execute("""
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price_info TEXT NOT NULL,
            warranty TEXT DEFAULT 'Full Warranty',
            photo_id TEXT
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product_id INTEGER,
            status TEXT DEFAULT 'New'
        )
    """)

    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        con.executemany(
            """
            INSERT INTO products(name,category,price_info,warranty)
            VALUES(?,?,?,?)
            """,
            DEFAULT_PRODUCTS
        )

    con.commit()
    return con


db()


# =========================
# MAIN MENU
# =========================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛍️ All Products",
                callback_data="all"
            )
        ],
        [
            InlineKeyboardButton(
                "🤖 AI Tools",
                callback_data="cat_ai"
            ),
            InlineKeyboardButton(
                "🎨 Design & Video",
                callback_data="cat_design"
            )
        ],
        [
            InlineKeyboardButton(
                "💼 Office & Productivity",
                callback_data="cat_office"
            ),
            InlineKeyboardButton(
                "📺 Entertainment",
                callback_data="cat_entertainment"
            )
        ],
        [
            InlineKeyboardButton(
                "🛠️ Software",
                callback_data="cat_software"
            ),
            InlineKeyboardButton(
                "📦 Other Products",
                callback_data="cat_other"
            )
        ],
        [
            InlineKeyboardButton(
                "📦 My Orders",
                callback_data="myorders"
            ),
            InlineKeyboardButton(
                "💬 Support",
                callback_data="support"
            )
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "✨ Welcome to Our Digital Store ✨\n\n"
        "🛡️ Full Warranty Included\n"
        "⚡ Stable Access\n"
        "🚀 Fast Delivery & Dedicated Support\n\n"
        "Choose a category below:"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu()
    )


# =========================
# PRODUCTS
# =========================

async def products_page(query, category=None):

    con = db()

    if category:
        rows = con.execute(
            """
            SELECT id,name
            FROM products
            WHERE category=?
            ORDER BY id DESC
            """,
            (category,)
        ).fetchall()
    else:
        rows = con.execute(
            """
            SELECT id,name
            FROM products
            ORDER BY id DESC
            """
        ).fetchall()

    con.close()

    buttons = [
        [
            InlineKeyboardButton(
                name,
                callback_data=f"product_{pid}"
            )
        ]
        for pid, name in rows
    ]

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Main Menu",
            callback_data="home"
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def show_product(query, pid):

    con = db()

    row = con.execute(
        """
        SELECT id,name,price_info,warranty,photo_id
        FROM products
        WHERE id=?
        """,
        (pid,)
    ).fetchone()

    con.close()

    if not row:
        await query.answer(
            "Product not found.",
            show_alert=True
        )
        return

    _, name, price_info, warranty, photo_id = row

    text = (
        f"🛍️ <b>{name}</b>\n\n"
        f"💰 {price_info}\n\n"
        f"🛡️ Warranty: {warranty}\n"
        f"⚡ Fast Delivery & Support"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛒 Order Now",
                callback_data=f"order_{pid}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Products",
                callback_data="all"
            )
        ],
    ])

    if photo_id:

        await query.message.reply_photo(
            photo_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=kb
        )

        try:
            await query.message.delete()
        except Exception:
            pass

    else:

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=kb
        )


# =========================
# PAYMENT MENU
# =========================

def payment_menu(pid):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟡 Binance",
                callback_data=f"pay_binance_{pid}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔴 USDT TRC20",
                callback_data=f"pay_trc20_{pid}"
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 USDT BEP20",
                callback_data=f"pay_bep20_{pid}"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data=f"product_{pid}"
            )
        ]
    ])


def payment_details(method):

    if method == "binance":

        return (
            "🟡 <b>Binance Payment</b>\n\n"
            "Please send the payment to:\n\n"
            f"🆔 <b>Binance UID:</b>\n"
            f"<code>{BINANCE_UID}</code>\n\n"
            "⚠️ Please make sure you send the exact amount.\n"
            "After payment, send your payment screenshot."
        )

    if method == "trc20":

        return (
            "🔴 <b>USDT TRC20 Payment</b>\n\n"
            "Please send USDT using the <b>TRC20 network</b>:\n\n"
            f"📍 <b>Address:</b>\n"
            f"<code>{USDT_TRC20}</code>\n\n"
            "⚠️ Network must be TRC20.\n"
            "After payment, send your payment screenshot."
        )

    if method == "bep20":

        return (
            "🟢 <b>USDT BEP20 Payment</b>\n\n"
            "Please send USDT using the <b>BEP20 network</b>:\n\n"
            f"📍 <b>Address:</b>\n"
            f"<code>{USDT_BEP20}</code>\n\n"
            "⚠️ Network must be BEP20.\n"
            "After payment, send your payment screenshot."
        )

    return "Payment method not found."


def payment_proof_button():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📤 Send Payment Proof",
                callback_data="send_proof"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 Main Menu",
                callback_data="home"
            )
        ]
    ])


# =========================
# CALLBACK HANDLER
# =========================

async def callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    data = query.data

    # Main menu
    if data == "home":

        await query.edit_message_text(
            "🏠 Main Menu",
            reply_markup=main_menu()
        )

    # All products
    elif data == "all":

        await query.edit_message_text(
            "🛍️ All Products:",
            reply_markup=await products_page(query)
        )

    # Categories
    elif data.startswith("cat_"):

        cat = data[4:]

        await query.edit_message_text(
            CATEGORIES.get(cat, "Products"),
            reply_markup=await products_page(query, cat)
        )

    # Product
    elif data.startswith("product_"):

        await show_product(
            query,
            int(data.split("_")[1])
        )

    # Order Now
    elif data.startswith("order_"):

        pid = int(data.split("_")[1])

        con = db()

        row = con.execute(
            "SELECT name FROM products WHERE id=?",
            (pid,)
        ).fetchone()

        con.close()

        if not row:

            await query.answer(
                "Product not found.",
                show_alert=True
            )
            return

        await query.edit_message_text(
            f"🛒 <b>{row[0]}</b>\n\n"
            "💳 <b>Select your payment method:</b>\n\n"
            "Choose one of the payment methods below.",
            parse_mode="HTML",
            reply_markup=payment_menu(pid)
        )

    # Binance
    elif data.startswith("pay_binance_"):

        pid = int(data.split("_")[2])

        await create_payment_order(
            query,
            context,
            pid,
            "Binance"
        )

    # TRC20
    elif data.startswith("pay_trc20_"):

        pid = int(data.split("_")[2])

        await create_payment_order(
            query,
            context,
            pid,
            "USDT TRC20"
        )

    # BEP20
    elif data.startswith("pay_bep20_"):

        pid = int(data.split("_")[2])

        await create_payment_order(
            query,
            context,
            pid,
            "USDT BEP20"
        )

    # Send payment proof
    elif data == "send_proof":

        if not context.user_data.get("pending_order_id"):

            await query.answer(
                "No pending order found.",
                show_alert=True
            )
            return

        await query.edit_message_text(
            "📤 <b>Payment Proof</b>\n\n"
            "Please send your payment screenshot here.\n\n"
            "📸 Send the screenshot as a photo.\n\n"
            "Our admin will verify your payment and process your order.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="home"
                    )
                ]
            ])
        )

    # Support
    elif data == "support":

        await query.edit_message_text(
            "💬 <b>Support</b>\n\n"
            "Please contact our support/admin to complete your order.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="home"
                    )
                ]
            ])
        )

    # My Orders
    elif data == "myorders":

        con = db()

        rows = con.execute("""
            SELECT o.id,p.name,o.status
            FROM orders o
            JOIN products p ON p.id=o.product_id
            WHERE o.user_id=?
            ORDER BY o.id DESC
            LIMIT 10
        """, (query.from_user.id,)).fetchall()

        con.close()

        text = "📦 <b>Your Orders</b>\n\n"

        if rows:

            text += "\n".join(
                f"#{oid} — {name} — {status}"
                for oid, name, status in rows
            )

        else:

            text += "No orders yet."

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🏠 Main Menu",
                        callback_data="home"
                    )
                ]
            ])
        )


# =========================
# CREATE ORDER
# =========================

async def create_payment_order(
    query,
    context,
    pid,
    payment_method
):

    con = db()

    row = con.execute(
        """
        SELECT name,price_info
        FROM products
        WHERE id=?
        """,
        (pid,)
    ).fetchone()

    if not row:

        con.close()

        await query.answer(
            "Product not found.",
            show_alert=True
        )

        return

    product_name = row[0]
    price_info = row[1]

    con.execute(
        """
        INSERT INTO orders(user_id,username,product_id,status)
        VALUES(?,?,?,'Payment Pending')
        """,
        (
            query.from_user.id,
            query.from_user.username or "",
            pid
        )
    )

    order_id = con.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    con.commit()
    con.close()

    # Save pending order for payment proof
    context.user_data["pending_order_id"] = order_id
    context.user_data["pending_product_id"] = pid
    context.user_data["pending_payment_method"] = payment_method

    # Admin notification
    if ADMIN_ID:

        username = query.from_user.username or "N/A"

        await context.bot.send_message(
            ADMIN_ID,
            f"🔔 <b>New Order #{order_id}</b>\n\n"
            f"👤 User: @{username}\n"
            f"🆔 User ID: {query.from_user.id}\n"
            f"🛍️ Product: {product_name}\n"
            f"💰 Price: {price_info}\n"
            f"💳 Payment Method: {payment_method}\n\n"
            f"⏳ Status: Payment Pending",
            parse_mode="HTML"
        )

    payment_method_key = ""

    if payment_method == "Binance":
        payment_method_key = "binance"

    elif payment_method == "USDT TRC20":
        payment_method_key = "trc20"

    elif payment_method == "USDT BEP20":
        payment_method_key = "bep20"

    text = (
        f"✅ <b>Order #{order_id} Created</b>\n\n"
        f"🛍️ <b>Product:</b> {product_name}\n"
        f"💰 <b>Price:</b> {price_info}\n"
        f"💳 <b>Payment:</b> {payment_method}\n\n"
        f"{payment_details(payment_method_key)}"
    )

    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=payment_proof_button()
    )


# =========================
# PAYMENT PROOF HANDLER
# =========================

async def receive_payment_proof(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    pending_order_id = context.user_data.get(
        "pending_order_id"
    )

    if not pending_order_id:

        await update.message.reply_text(
            "❌ No pending order found.\n\n"
            "Please place an order first."
        )

        return

    payment_method = context.user_data.get(
        "pending_payment_method",
        "N/A"
    )

    pid = context.user_data.get(
        "pending_product_id"
    )

    con = db()

    row = con.execute(
        """
        SELECT name,price_info
        FROM products
        WHERE id=?
        """,
        (pid,)
    ).fetchone()

    con.close()

    product_name = row[0] if row else "Unknown Product"
    price_info = row[1] if row else "N/A"

    username = update.effective_user.username or "N/A"
    user_id = update.effective_user.id

    # Update order status
    con = db()

    con.execute(
        """
        UPDATE orders
        SET status='Payment Proof Submitted'
        WHERE id=?
        """,
        (pending_order_id,)
    )

    con.commit()
    con.close()

    # Send proof to admin
    if ADMIN_ID:

        caption = (
            f"📸 <b>Payment Proof Received</b>\n\n"
            f"🧾 <b>Order:</b> #{pending_order_id}\n"
            f"👤 <b>User:</b> @{username}\n"
            f"🆔 <b>User ID:</b> {user_id}\n"
            f"🛍️ <b>Product:</b> {product_name}\n"
            f"💰 <b>Price:</b> {price_info}\n"
            f"💳 <b>Payment:</b> {payment_method}\n\n"
            f"⏳ <b>Status:</b> Payment Proof Submitted"
        )

        await context.bot.send_photo(
            ADMIN_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption,
            parse_mode="HTML"
        )

    await update.message.reply_text(
        f"✅ <b>Payment proof received!</b>\n\n"
        f"🧾 Order #{pending_order_id}\n\n"
        "Our admin will verify your payment and process your order.\n"
        "Please wait for confirmation.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🏠 Main Menu",
                    callback_data="home"
                )
            ]
        ])
    )

    # Clear pending order
    context.user_data.pop("pending_order_id", None)
    context.user_data.pop("pending_product_id", None)
    context.user_data.pop("pending_payment_method", None)


# =========================
# ADMIN: ADD PRODUCT
# =========================

ADD_NAME, ADD_CATEGORY, ADD_PRICE, ADD_WARRANTY, ADD_PHOTO = range(5)


def is_admin(update):

    return (
        ADMIN_ID
        and update.effective_user
        and update.effective_user.id == ADMIN_ID
    )


async def add_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(update):

        await update.message.reply_text(
            "⛔ Admin only."
        )

        return ConversationHandler.END

    await update.message.reply_text(
        "Send the new product name:"
    )

    return ADD_NAME


async def add_name(update, context):

    context.user_data["name"] = (
        update.message.text.strip()
    )

    await update.message.reply_text(
        "Send category:\n"
        "ai / design / office / entertainment / software / other"
    )

    return ADD_CATEGORY


async def add_category(update, context):

    cat = update.message.text.strip().lower()

    if cat not in CATEGORIES:

        await update.message.reply_text(
            "Invalid category.\n"
            "Use: ai, design, office, entertainment, software, other"
        )

        return ADD_CATEGORY

    context.user_data["category"] = cat

    await update.message.reply_text(
        "Send price/duration information, e.g.:\n"
        "1 Month — $5\n"
        "1 Year — $20"
    )

    return ADD_PRICE


async def add_price(update, context):

    context.user_data["price"] = (
        update.message.text.strip()
    )

    await update.message.reply_text(
        "Send warranty type "
        "(e.g. Full Warranty / No Warranty):"
    )

    return ADD_WARRANTY


async def add_warranty(update, context):

    context.user_data["warranty"] = (
        update.message.text.strip()
    )

    await update.message.reply_text(
        "Now send the product photo.\n"
        "You can also send /skip_photo"
    )

    return ADD_PHOTO


async def add_photo(update, context):

    photo_id = update.message.photo[-1].file_id

    save_product(
        context,
        photo_id
    )

    await update.message.reply_text(
        "✅ Product added successfully!"
    )

    context.user_data.clear()

    return ConversationHandler.END


async def skip_photo(update, context):

    save_product(
        context,
        None
    )

    await update.message.reply_text(
        "✅ Product added without a photo."
    )

    context.user_data.clear()

    return ConversationHandler.END


def save_product(context, photo_id):

    con = db()

    con.execute(
        """
        INSERT INTO products(
            name,
            category,
            price_info,
            warranty,
            photo_id
        )
        VALUES(?,?,?,?,?)
        """,
        (
            context.user_data["name"],
            context.user_data["category"],
            context.user_data["price"],
            context.user_data["warranty"],
            photo_id
        )
    )

    con.commit()
    con.close()


async def cancel(update, context):

    context.user_data.clear()

    await update.message.reply_text(
        "Cancelled."
    )

    return ConversationHandler.END


async def admin_products(update, context):

    if not is_admin(update):
        return

    con = db()

    rows = con.execute(
        """
        SELECT id,name
        FROM products
        ORDER BY id DESC
        """
    ).fetchall()

    con.close()

    text = "🛠️ Products:\n\n"

    text += "\n".join(
        f"{pid}. {name}"
        for pid, name in rows
    )

    await update.message.reply_text(text)


# =========================
# MAIN
# =========================

def main():

    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":

        raise RuntimeError(
            "Set BOT_TOKEN environment variable first."
        )

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Add product conversation
    add_conv = ConversationHandler(

        entry_points=[
            CommandHandler(
                "add",
                add_start
            )
        ],

        states={

            ADD_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_name
                )
            ],

            ADD_CATEGORY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_category
                )
            ],

            ADD_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_price
                )
            ],

            ADD_WARRANTY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_warranty
                )
            ],

            ADD_PHOTO: [
                MessageHandler(
                    filters.PHOTO,
                    add_photo
                ),
                CommandHandler(
                    "skip_photo",
                    skip_photo
                ),
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel
            )
        ],
    )

    # Commands
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "products",
            admin_products
        )
    )

    # Admin add product
    app.add_handler(add_conv)

    # Payment proof photo
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            receive_payment_proof
        )
    )

    # Callback buttons
    app.add_handler(
        CallbackQueryHandler(callback)
    )

    app.run_polling()


if __name__ == "__main__":
    main()
