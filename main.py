import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQuery_Handler,
    ConversationHandler,
    ContextTypes,
    filters
)

# --- НАСТРОЙКИ ---
TOKEN = '8067572893:AAH0Lx_Dq2lENkuTDoHQO1v46NTe8WLWEpo'
ADMIN_ID = 7908057052
DB_FILE = 'database.json'

# Этапы создания матча (для ConversationHandler)
TEAM1, TEAM2, TIME = range(3)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- БАЗА ДАННЫХ ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"players": {}, "clubs": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_db()

# --- ХЕНДЛЕРЫ ИГРОКОВ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in db["players"]:
        club = db["players"][user_id]["club"]
        reply_kb = [['/Ready', '/UnReady']]
        await update.message.reply_text(
            f"✅ Вы привязаны к клубу: {club}",
            reply_markup=ReplyKeyboardMarkup(reply_kb, resize_keyboard=True)
        )
    else:
        await update.message.reply_text("❌ Вы не привязаны. Попросите @Verybigsun привязать вас.")

async def ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in db["players"]: return
    name = update.effective_user.full_name
    club = db["players"][user_id]["club"]
    await update.message.reply_text("✅ Принято!")
    await context.bot.send_message(ADMIN_ID, f"🟢 ГОТОВ: {name} ({club})")

async def unready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in db["players"]: return
    name = update.effective_user.full_name
    club = db["players"][user_id]["club"]
    await update.message.reply_text("❌ Отметил, что вас не будет.")
    await context.bot.send_message(ADMIN_ID, f"🔴 ОТКАЗ: {name} ({club})")

# --- АДМИН КОМАНДЫ ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(
        "🛠 Админка:\n"
        "/add_club [Название] — добавить клуб\n"
        "/bind [ID] [Название] — привязать игрока\n"
        "/match — создать сбор"
    )

async def add_club(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    club_name = " ".join(context.args)
    if club_name:
        if club_name not in db["clubs"]:
            db["clubs"].append(club_name)
            save_db(db)
            await update.message.reply_text(f"✅ Клуб {club_name} добавлен.")
    else:
        await update.message.reply_text("Напишите название: /add_club Динамо")

async def bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        t_id = context.args[0]
        c_name = " ".join(context.args[1:])
        db["players"][t_id] = {"club": c_name}
        save_db(db)
        await update.message.reply_text(f"✅ Игрок {t_id} привязан к {c_name}")
    except:
        await update.message.reply_text("Ошибка. Формат: /bind 12345 Название")

# --- ЛОГИКА СОЗДАНИЯ МАТЧА ---
async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not db["clubs"]:
        await update.message.reply_text("Сначала добавьте клубы.")
        return ConversationHandler.END
    
    kb = [[InlineKeyboardButton(c, callback_data=c)] for c in db["clubs"]]
    await update.message.reply_text("Выберите первую команду:", reply_markup=InlineKeyboardMarkup(kb))
    return TEAM1

async def team1_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['t1'] = query.data
    kb = [[InlineKeyboardButton(c, callback_data=c)] for c in db["clubs"]]
    await query.edit_message_text(f"Команда 1: {query.data}\nВыберите соперника:", reply_markup=InlineKeyboardMarkup(kb))
    return TEAM2

async def team2_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == context.user_data['t1']:
        await query.message.reply_text("Нельзя выбрать ту же команду.")
        return TEAM2
    context.user_data['t2'] = query.data
    await query.edit_message_text(f"Матч: {context.user_data['t1']} vs {query.data}\nНапишите время и дату:")
    return TIME

async def time_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_val = update.message.text
    t1 = context.user_data['t1']
    t2 = context.user_data['t2']
    
    text = f"📢 МАТЧ!\n🏟 {t1} vs {t2}\n⏰ Время: {time_val}\n\nДайте отпись: /Ready или /UnReady"
    
    for uid in db["players"]:
        try:
            await context.bot.send_message(chat_id=int(uid), text=text)
        except: pass
        
    await update.message.reply_text("✅ Сбор разослан!")
    return ConversationHandler.END

# --- ЗАПУСК ---
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("Ready", ready))
    app.add_handler(CommandHandler("UnReady", unready))
    app.add_handler(CommandHandler("Admin", admin_panel))
    app.add_handler(CommandHandler("add_club", add_club))
    app.add_handler(CommandHandler("bind", bind))

    match_conv = ConversationHandler(
        entry_points=[CommandHandler("match", match_start)],
        states={
            TEAM1: [CallbackQueryHandler(team1_selected)],
            TEAM2: [CallbackQueryHandler(team2_selected)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time_set)],
        },
        fallbacks=[],
    )
    app.add_handler(match_conv)

    print("Бот запущен на библиотеке python-telegram-bot")
    app.run_polling()

if __name__ == '__main__':
    main()
