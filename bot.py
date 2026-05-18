import os
import logging
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

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ غير مصرح لك.")
        return
    keyboard = [
        [InlineKeyboardButton("🔍 ابحث عن منتجات", callback_data="search")],
        [InlineKeyboardButton("🤖 تشغيل تلقائي", callback_data="auto")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
    ]
    await update.message.reply_text(
        "🛒 *مرحباً! اختر ما تريد فعله:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "search":
        await query.edit_message_text(
            "🔍 أرسل لي الكلمة التي تريد البحث عنها في Creative Fabrica\n"
            "مثال: floral svg, christmas fonts, watercolor"
        )
        context.user_data["waiting_for"] = "search_query"

    elif data == "auto":
        await query.edit_message_text("🤖 جاري تشغيل الوضع التلقائي...")
        await run_auto_mode(query, context)

    elif data == "stats":
        stats = context.bot_data.get("stats", {"uploaded": 0, "earned": 0.0})
        await query.edit_message_text(
            f"📊 *الإحصائيات:*\n\n"
            f"✅ منتجات مرفوعة: {stats['uploaded']}\n"
            f"💰 أرباح تقديرية: ${stats['earned']:.2f}",
            parse_mode="Markdown"
        )

    elif data.startswith("select_"):
        # اختيار منتج من نتائج البحث
        index = int(data.split("_")[1])
        products = context.user_data.get("search_results", [])
        
        if not products or index >= len(products):
            await query.edit_message_text("❌ انتهت الجلسة، ابحث مجدداً.")
            return
        
        product = products[index]
        await query.edit_message_text(
            f"📦 تم اختيار: *{product['name']}*\n\n"
            f"⏳ جاري المعالجة...",
            parse_mode="Markdown"
        )
        await process_product(query, context, product)

    elif data == "back":
        await start_from_query(query, context)

async def process_product(query, context, product):
    """معالجة المنتج: تنزيل → محتوى → رفع → فيديو"""
    try:
        # تنزيل الملف
        await query.message.reply_text("📥 جاري تنزيل الملف من Creative Fabrica...")
        file_path = await download_product(product)
        await query.message.reply_text("✅ تم التنزيل!")

        # توليد المحتوى
        await query.message.reply_text("🤖 جاري توليد العنوان والوصف بالذكاء الاصطناعي...")
        content = await generate_product_content(product)
        await query.message.reply_text(
            f"✅ *تم توليد المحتوى:*\n\n"
            f"📝 {content['title']}\n"
            f"💰 السعر: ${content['price']}",
            parse_mode="Markdown"
        )

        # رفع على Gumroad
        await query.message.reply_text("📤 جاري الرفع على Gumroad...")
        result = await upload_to_gumroad(file_path, content)
        await query.message.reply_text(
            f"🎉 *تم الرفع بنجاح!*\n\n"
            f"🔗 الرابط: {result.get('url', 'N/A')}\n"
            f"💰 السعر: ${content['price']}",
            parse_mode="Markdown"
        )

        # إنشاء الفيديو
        await query.message.reply_text("🎬 جاري إنشاء الفيديو الترويجي...")
        video_path = await create_promo_video(product, content)
        with open(video_path, "rb") as v:
            await query.message.reply_video(
                video=v,
                caption=f"🎬 فيديو ترويجي جاهز للنشر على TikTok!\n\n{content.get('tiktok_tags', '')}"
            )

        # تحديث الإحصائيات
        stats = context.bot_data.get("stats", {"uploaded": 0, "earned": 0.0})
        stats["uploaded"] += 1
        stats["earned"] += float(content.get("price", 0))
        context.bot_data["stats"] = stats

        # زر للعودة
        keyboard = [[InlineKeyboardButton("🔍 بحث جديد", callback_data="search"),
                     InlineKeyboardButton("🏠 الرئيسية", callback_data="back")]]
        await query.message.reply_text(
            "✅ *اكتملت العملية بنجاح!*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        await query.message.reply_text(f"❌ خطأ: {str(e)}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    waiting = context.user_data.get("waiting_for")

    if waiting == "search_query":
        query_text = update.message.text
        context.user_data["waiting_for"] = None
        await update.message.reply_text(f"🔍 جاري البحث عن: *{query_text}*...", parse_mode="Markdown")

        try:
            products = await search_products(query_text)
            if not products:
                await update.message.reply_text("❌ لم يتم العثور على منتجات، جرب كلمة أخرى.")
                return

            keyboard = []
            for i, p in enumerate(products[:8]):
                keyboard.append([InlineKeyboardButton(
                    f"📦 {p['name'][:35]}",
                    callback_data=f"select_{i}"
                )])
            
            context.user_data["search_results"] = products
            await update.message.reply_text(
                f"✅ وجدت *{len(products)}* منتج. اختر واحداً:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {str(e)}")

async def start_from_query(query, context):
    keyboard = [
        [InlineKeyboardButton("🔍 ابحث عن منتجات", callback_data="search")],
        [InlineKeyboardButton("🤖 تشغيل تلقائي", callback_data="auto")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
    ]
    await query.edit_message_text(
        "🛒 *مرحباً! اختر ما تريد فعله:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def run_auto_mode(query, context):
    niches = ["floral svg", "christmas svg", "watercolor clipart"]
    for niche in niches[:1]:
        await query.message.reply_text(f"🔍 البحث في نيش: *{niche}*", parse_mode="Markdown")
        try:
            products = await search_products(niche)
            if products:
                await process_product(query, context, products[0])
        except Exception as e:
            await query.message.reply_text(f"❌ خطأ: {str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("🤖 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
