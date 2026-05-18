import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from ai_helper import generate_product_content
from gumroad_uploader import upload_to_gumroad
from video_maker import create_promo_video

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ غير مصرح لك.")
        return
    keyboard = [
        [InlineKeyboardButton("📤 رفع ملف جديد", callback_data="upload")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
    ]
    await update.message.reply_text(
        "🛒 *مرحباً بك في بوت المتجر!*\n\n"
        "الطريقة:\n"
        "1️⃣ نزّل الملف من Creative Fabrica\n"
        "2️⃣ أرسله هنا\n"
        "3️⃣ البوت يرفعه على Gumroad تلقائياً 🚀\n"
        "4️⃣ ينشئ فيديو TikTok جاهز!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "upload":
        await query.edit_message_text(
            "📤 *أرسل الملف الآن!*\n\n"
            "يمكنك إرسال:\n"
            "• ملف ZIP مباشرة\n"
            "• أو أي ملف تصميم\n\n"
            "⚠️ بعد الإرسال أخبرني اسم المنتج ونوعه",
            parse_mode="Markdown"
        )
        context.user_data["waiting_for"] = "file"

    elif data == "stats":
        stats = context.bot_data.get("stats", {"uploaded": 0, "earned": 0.0})
        await query.edit_message_text(
            f"📊 *الإحصائيات:*\n\n"
            f"✅ منتجات مرفوعة: {stats['uploaded']}\n"
            f"💰 أرباح تقديرية: ${stats['earned']:.2f}",
            parse_mode="Markdown"
        )

    elif data == "confirm_upload":
        product = context.user_data.get("pending_product")
        file_path = context.user_data.get("pending_file")
        if product and file_path:
            await query.edit_message_text("⏳ جاري المعالجة...")
            await process_product(query, context, product, file_path)
        else:
            await query.edit_message_text("❌ لا يوجد ملف معلق، أرسل الملف مجدداً.")

    elif data == "back":
        keyboard = [
            [InlineKeyboardButton("📤 رفع ملف جديد", callback_data="upload")],
            [InlineKeyboardButton("📊 إحصائيات", callback_data="stats")],
        ]
        await query.edit_message_text(
            "🛒 *اختر ما تريد فعله:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    # استقبال الملف
    file = update.message.document or (update.message.photo[-1] if update.message.photo else None)
    
    if not file:
        await update.message.reply_text("❌ لم أستطع استقبال الملف، جرب مرة أخرى.")
        return

    await update.message.reply_text("📥 جاري استقبال الملف...")
    
    # تحميل الملف
    file_obj = await file.get_file()
    if update.message.document:
        filename = update.message.document.file_name or "product.zip"
    else:
        filename = "product_image.jpg"
    
    file_path = f"{DOWNLOAD_DIR}/{filename}"
    await file_obj.download_to_drive(file_path)
    
    context.user_data["pending_file"] = file_path
    context.user_data["waiting_for"] = "product_name"
    
    await update.message.reply_text(
        "✅ تم استقبال الملف!\n\n"
        "📝 أرسل لي *اسم المنتج* (بالإنجليزية)\n"
        "مثال: Floral SVG Bundle, Christmas Fonts Pack",
        parse_mode="Markdown"
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    waiting = context.user_data.get("waiting_for")
    text = update.message.text

    if waiting == "product_name":
        context.user_data["waiting_for"] = "product_niche"
        context.user_data["product_name"] = text
        await update.message.reply_text(
            f"✅ الاسم: *{text}*\n\n"
            "🏷️ أرسل لي *نيش* المنتج (بالإنجليزية)\n"
            "مثال: SVG, Fonts, Clipart, Embroidery, Planner",
            parse_mode="Markdown"
        )

    elif waiting == "product_niche":
        context.user_data["waiting_for"] = None
        name = context.user_data.get("product_name", "Product")
        niche = text
        file_path = context.user_data.get("pending_file")

        product = {
            "name": name,
            "query": niche,
            "url": "",
            "image": ""
        }
        context.user_data["pending_product"] = product

        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الرفع", callback_data="confirm_upload")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="back")],
        ]
        await update.message.reply_text(
            f"📋 *ملخص المنتج:*\n\n"
            f"📦 الاسم: {name}\n"
            f"🏷️ النيش: {niche}\n"
            f"📁 الملف: جاهز ✅\n\n"
            f"هل تريد المتابعة؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def process_product(query, context, product, file_path):
    """توليد المحتوى + رفع على Gumroad + فيديو"""
    try:
        # توليد المحتوى
        await query.message.reply_text("🤖 جاري توليد العنوان والوصف...")
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
            f"🔗 {result.get('url', 'N/A')}\n"
            f"💰 السعر: ${content['price']}",
            parse_mode="Markdown"
        )

        # إنشاء فيديو TikTok
        await query.message.reply_text("🎬 جاري إنشاء فيديو TikTok...")
        video_path = await create_promo_video(product, content)
        with open(video_path, "rb") as v:
            await query.message.reply_video(
                video=v,
                caption=f"🎬 فيديو جاهز للنشر على TikTok!\n\n{content.get('tiktok_tags', '')}"
            )

        # تحديث الإحصائيات
        stats = context.bot_data.get("stats", {"uploaded": 0, "earned": 0.0})
        stats["uploaded"] += 1
        stats["earned"] += float(content.get("price", 0))
        context.bot_data["stats"] = stats

        keyboard = [[InlineKeyboardButton("📤 رفع منتج جديد", callback_data="upload")]]
        await query.message.reply_text(
            "✅ *اكتملت العملية بنجاح!*\n\nهل تريد رفع منتج آخر؟",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        await query.message.reply_text(f"❌ خطأ: {str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(MessageHandler(filters.PHOTO, file_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("🤖 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
