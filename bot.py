import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from cf_scraper import search_products, download_product
from ai_helper import generate_product_content
from gumroad_uploader import upload_to_gumroad
from video_maker import create_promo_video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ===== التحقق من المشرف =====
def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

# ===== أوامر البوت =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
        return

    keyboard = [
        [InlineKeyboardButton("🔍 ابحث عن منتجات", callback_data="search")],
        [InlineKeyboardButton("🤖 تشغيل تلقائي", callback_data="auto")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🛒 *مرحباً بك في بوت المتجر!*\n\n"
        "اختر ما تريد فعله:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "search":
        await query.edit_message_text(
            "🔍 أرسل لي الكلمة التي تريد البحث عنها في Creative Fabrica\n"
            "مثال: floral svg, christmas fonts, watercolor"
        )
        context.user_data["waiting_for"] = "search_query"

    elif query.data == "auto":
        await query.edit_message_text("🤖 جاري تشغيل الوضع التلقائي...")
        await run_auto_mode(query, context)

    elif query.data == "stats":
        stats = context.bot_data.get("stats", {"uploaded": 0, "earned": 0})
        await query.edit_message_text(
            f"📊 *الإحصائيات:*\n\n"
            f"✅ منتجات مرفوعة: {stats['uploaded']}\n"
            f"💰 أرباح تقديرية: ${stats['earned']}",
            parse_mode="Markdown"
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    waiting = context.user_data.get("waiting_for")

    if waiting == "search_query":
        query = update.message.text
        context.user_data["waiting_for"] = None
        await update.message.reply_text(f"🔍 جاري البحث عن: *{query}*...", parse_mode="Markdown")

        try:
            products = await search_products(query)
            if not products:
                await update.message.reply_text("❌ لم يتم العثور على منتجات.")
                return

            keyboard = []
            for i, p in enumerate(products[:5]):
                keyboard.append([InlineKeyboardButton(
                    f"📦 {p['name'][:40]}",
                    callback_data=f"select_{i}"
                )])
            context.user_data["search_results"] = products
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ وجدت *{len(products)}* منتج. اختر واحداً:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")

async def run_auto_mode(query, context):
    niches = ["floral svg", "christmas fonts", "watercolor clipart", "baby shower svg"]
    
    for niche in niches[:2]:
        await query.message.reply_text(f"🔍 جاري البحث في نيش: *{niche}*", parse_mode="Markdown")
        
        try:
            products = await search_products(niche)
            if not products:
                continue

            product = products[0]
            await query.message.reply_text(f"📦 تم اختيار: *{product['name']}*", parse_mode="Markdown")

            file_path = await download_product(product)
            await query.message.reply_text("✅ تم التنزيل! جاري إنشاء المحتوى...")

            content = await generate_product_content(product)
            await query.message.reply_text("✅ تم إنشاء المحتوى! جاري الرفع على Gumroad...")

            result = await upload_to_gumroad(file_path, content)
            await query.message.reply_text(
                f"🎉 *تم الرفع بنجاح!*\n\n"
                f"🔗 الرابط: {result.get('url', 'N/A')}\n"
                f"💰 السعر: ${content['price']}",
                parse_mode="Markdown"
            )

            await query.message.reply_text("🎬 جاري إنشاء الفيديو الترويجي...")
            video_path = await create_promo_video(product, content)
            await query.message.reply_video(
                video=open(video_path, "rb"),
                caption=f"🎬 فيديو ترويجي لـ: {product['name']}\n\nانشره على TikTok! 🎵"
            )

            stats = context.bot_data.get("stats", {"uploaded": 0, "earned": 0})
            stats["uploaded"] += 1
            stats["earned"] += float(content.get("price", 0))
            context.bot_data["stats"] = stats

        except Exception as e:
            await query.message.reply_text(f"❌ خطأ في النيش {niche}: {str(e)}")
            continue

    await query.message.reply_text("✅ انتهى الوضع التلقائي!")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("🤖 البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
