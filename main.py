import json
import logging
import uuid
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, ConversationHandler, 
    ContextTypes, MessageHandler, filters,
)

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8330028687:AAEU9Qah_ykkUgA32Dw2ev9x1NVkNplrvs8"
DATA_FILE = "data.json"
FIXED_COACH_ID = 7908057052  # ID тренера

# Состояния
PROFILE_NAME = 0
MATCH_DATE, MATCH_TIME, MATCH_LOCATION = range(1, 4)

# ==================== РАБОТА С ДАННЫМИ ====================
def load_data() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for key in ["players", "matches"]:
                if key not in data: data[key] = {} if key == "players" else []
            if "team" not in data: data["team"] = {"players": []}
            return data
    except:
        return {"players": {}, "team": {"players": []}, "matches": []}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    welcome_text = (
        "⚽️ **Добро пожаловать в футбольный менеджер!**\n\n"
        "**Что нужно сделать:**\n"
        "1️⃣ Напишите /profile — чтобы зарегистрироваться в базе.\n"
        "2️⃣ После этого тренер сможет добавить вас в команду.\n\n"
        "**Доступные команды:**\n"
        "/team — Посмотреть текущий состав\n"
        "/matches — Список предстоящих матчей\n"
        "/profile — Создать/изменить свой профиль\n"
    )
    
    if user_id == FIXED_COACH_ID:
        welcome_text += (
            "\n👑 **Вы — Тренер! Вам доступны:**\n"
            "/add_player @nick — Добавить игрока по нику\n"
            "/add_player Имя Позиция — Добавить вручную\n"
            "/delete_player 1 — Удалить игрока №1 из состава\n"
            "/match — Создать новый матч"
        )
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# -------------------- УПРАВЛЕНИЕ СОСТАВОМ --------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    team_ids = data["team"]["players"]
    all_players = data["players"]
    
    if not team_ids:
        await update.message.reply_text("❌ Состав пуст. Тренеру нужно добавить игроков через /add_player")
        return

    text = "🧑‍🤝‍🧑 **Текущий состав команды:**\n\n"
    for i, uid in enumerate(team_ids, 1):
        p = all_players.get(str(uid))
        if p:
            name = p.get("name", "Игрок")
            pos = p.get("position", "Позиция не указана")
            contact = f" (@{p['contact']})" if p.get("contact") else ""
            text += f"{i}. **{name}** — {pos}{contact}\n"
        else:
            text += f"{i}. Неизвестный ID: {uid}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != FIXED_COACH_ID:
        await update.message.reply_text("❌ Только тренер может управлять составом.")
        return

    if not context.args:
        await update.message.reply_text("Использование:\n`/add_player @username`\n`/add_player Иван Нападающий`", parse_mode="Markdown")
        return

    data = load_data()
    arg = context.args[0]

    if arg.startswith("@"):
        username = arg.lstrip("@").lower()
        target_id = None
        for uid, info in data["players"].items():
            if str(info.get("contact", "")).lower() == username:
                target_id = str(uid)
                break
        
        if not target_id:
            await update.message.reply_text(f"❌ Игрок {arg} не найден. Он должен написать /profile боту.")
            return
        
        if target_id not in data["team"]["players"]:
            data["team"]["players"].append(target_id)
            save_data(data)
            await update.message.reply_text(f"✅ {arg} успешно добавлен в команду!")
        else:
            await update.message.reply_text("Этот игрок уже есть в списке.")
    else:
        name = arg
        pos = " ".join(context.args[1:]) if len(context.args) > 1 else "Позиция не указана"
        manual_id = f"m_{uuid.uuid4().hex[:5]}"
        data["players"][manual_id] = {"name": name, "position": pos, "contact": None}
        data["team"]["players"].append(manual_id)
        save_data(data)
        await update.message.reply_text(f"✅ {name} добавлен в команду вручную.")

async def delete_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != FIXED_COACH_ID: return
    
    data = load_data()
    try:
        num = int(context.args[0]) - 1
        if 0 <= num < len(data["team"]["players"]):
            removed = data["team"]["players"].pop(num)
            save_data(data)
            await update.message.reply_text("✅ Игрок удален из состава.")
        else:
            await update.message.reply_text("❌ Неверный номер. Посмотрите номер в списке /team")
    except:
        await update.message.reply_text("Пример: `/delete_player 1` (удалить первого игрока)", parse_mode="Markdown")

# -------------------- ДИАЛОГ ПРОФИЛЯ --------------------
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ваше Имя и Фамилию для регистрации в команде:")
    return PROFILE_NAME

async def profile_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user = update.effective_user
    data = load_data()
    
    data["players"][str(user.id)] = {
        "name": name,
        "position": "Не указана",
        "contact": user.username.lower() if user.username else f"id{user.id}"
    }
    save_data(data)
    await update.message.reply_text(f"✅ Спасибо, {name}! Теперь тренер может добавить вас в команду по нику @{user.username}")
    return ConversationHandler.END

# -------------------- МАТЧИ --------------------
async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != FIXED_COACH_ID: return ConversationHandler.END
    await update.message.reply_text("Введите дату (например, 15.06):")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_date"] = update.message.text
    await update.message.reply_text("Введите время (например, 19:00):")
    return MATCH_TIME

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_time"] = update.message.text
    await update.message.reply_text("Введите место:")
    return MATCH_LOCATION

async def match_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    info = f"{context.user_data['m_date']} в {context.user_data['m_time']}"
    data["matches"].append({"info": info, "loc": update.message.text})
    save_data(data)
    await update.message.reply_text("✅ Матч добавлен!")
    return ConversationHandler.END

async def list_matches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["matches"]:
        await update.message.reply_text("Нет запланированных матчей.")
        return
    text = "📅 **Расписание матчей:**\n\n"
    for m in data["matches"]:
        text += f"• {m['info']} — {m['loc']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ==================== ЗАПУСК ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Сценарии
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_save)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))
    
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("match", match_start)],
        states={
            MATCH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_date)],
            MATCH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_time)],
            MATCH_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_loc)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("add_player", add_player))
    app.add_handler(CommandHandler("delete_player", delete_player))
    app.add_handler(CommandHandler("matches", list_matches))
    app.add_handler(CommandHandler("cancel", cancel))

    print("🚀 Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
