import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8330028687:AAEU9Qah_ykkUgA32Dw2ev9x1NVkNplrvs8"
DATA_FILE = "data.json"
MAX_PLAYERS = 20
FIXED_COACH_ID = 7908057052  # ID тренера

# Состояния диалогов
PROFILE_NAME = 0
MATCH_DATE, MATCH_TIME, MATCH_LOCATION = range(1, 4)

# ==================== РАБОТА С ДАННЫМИ ====================
def load_data() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Гарантируем наличие нужных ключей
            if "players" not in data: data["players"] = {}
            if "team" not in data: data["team"] = {"players": []}
            if "matches" not in data: data["matches"] = []
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"players": {}, "team": {"players": [], "coach": None}, "matches": []}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_coach(user_id: int) -> bool:
    return user_id == FIXED_COACH_ID

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "⚽️ **Бот управления командой**\n\n"
        "**Для всех:**\n"
        "/profile — создать/посмотреть профиль\n"
        "/team — текущий состав\n"
        "/matches — расписание\n\n"
        "**Для тренера:**\n"
        "/add_player @username — добавить по нику\n"
        "/add_player Имя Позиция — добавить вручную\n"
        "/delete_player [номер] — удалить из списка\n"
        "/match — создать матч\n"
        "/cancel — отмена ввода"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# -------------------- УПРАВЛЕНИЕ СОСТАВОМ --------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    team_ids = data["team"]["players"]
    all_players = data["players"]
    
    if not team_ids:
        await update.message.reply_text("Состав пуст. Тренер может добавить игроков через /add_player")
        return

    lines = ["🧑‍🤝‍🧑 **Текущий состав команды:**"]
    for idx, uid in enumerate(team_ids, 1):
        # В JSON ключи всегда строки, поэтому uid кастим в str
        p = all_players.get(str(uid))
        if p:
            name = p.get("name", "Без имени")
            pos = p.get("position") or "Позиция не указана"
            contact = f" (@{p['contact']})" if p.get("contact") else ""
            lines.append(f"{idx}. {name} — *{pos}*{contact}")
        else:
            lines.append(f"{idx}. [ID: {uid}] — Профиль не заполнен")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await update.message.reply_text("❌ Доступ только для тренера.")
        return

    data = load_data()
    if not context.args:
        await update.message.reply_text("Использование:\n`/add_player @username`\n`/add_player Иван Вратарь`", parse_mode="Markdown")
        return

    if len(data["team"]["players"]) >= MAX_PLAYERS:
        await update.message.reply_text(f"Превышен лимит ({MAX_PLAYERS} чел).")
        return

    arg = context.args[0]
    
    # Добавление по @username
    if arg.startswith("@"):
        username = arg.lstrip("@").lower()
        target_id = None
        for uid, p in data["players"].items():
            if str(p.get("contact")).lower() == username:
                target_id = str(uid)
                break
        
        if not target_id:
            await update.message.reply_text(f"Игрок {arg} не найден. Он должен сначала создать /profile")
            return
        
        if target_id in data["team"]["players"]:
            await update.message.reply_text("Игрок уже в составе.")
            return

        data["team"]["players"].append(target_id)
        save_data(data)
        await update.message.reply_text(f"✅ {arg} добавлен в команду.")
    
    # Добавление вручную
    else:
        name = context.args[0]
        pos = " ".join(context.args[1:]) if len(context.args) > 1 else "Не указана"
        manual_id = f"manual_{uuid.uuid4().hex[:6]}"
        
        data["players"][manual_id] = {"name": name, "position": pos, "contact": None}
        data["team"]["players"].append(manual_id)
        save_data(data)
        await update.message.reply_text(f"✅ Игрок {name} добавлен вручную.")

async def delete_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        return

    data = load_data()
    try:
        idx = int(context.args[0]) - 1
        if 0 <= idx < len(data["team"]["players"]):
            removed_id = data["team"]["players"].pop(idx)
            save_data(data)
            await update.message.reply_text("✅ Игрок удален.")
        else:
            await update.message.reply_text("Неверный номер из списка /team")
    except (IndexError, ValueError):
        await update.message.reply_text("Укажите номер игрока. Пример: /delete_player 1")

# -------------------- ПРОФИЛЬ --------------------
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    
    if user_id in data["players"]:
        p = data["players"][user_id]
        await update.message.reply_text(
            f"✅ Ваш профиль уже есть:\nИмя: {p['name']}\n"
            f"Контакт: @{p.get('contact', 'нет')}\n\n"
            "Чтобы изменить, напишите имя заново или /cancel для отмены."
        )
    else:
        await update.message.reply_text("Введите ваше Имя и Фамилию:")
    return PROFILE_NAME

async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user = update.effective_user
    data = load_data()
    
    data["players"][str(user.id)] = {
        "name": name,
        "position": None,
        "contact": user.username if user.username else f"id{user.id}"
    }
    save_data(data)
    await update.message.reply_text(f"✅ Профиль '{name}' сохранен! Теперь тренер может добавить вас в команду.")
    return ConversationHandler.END

# -------------------- МАТЧИ --------------------
async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id):
        await update.message.reply_text("❌ Только для тренера.")
        return ConversationHandler.END
    await update.message.reply_text("Дата матча (ДД.ММ.ГГГГ, например 20.10.2026):")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_date"] = update.message.text.strip()
    await update.message.reply_text("Время (например, 18:30):")
    return MATCH_TIME

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_time"] = update.message.text.strip()
    await update.message.reply_text("Место (название поля/адрес):")
    return MATCH_LOCATION

async def match_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    m_date = context.user_data.get("m_date")
    m_time = context.user_data.get("m_time")
    m_loc = update.message.text.strip()
    
    try:
        dt_str = f"{m_date} {m_time}"
        # Проверка формата
        datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        data["matches"].append({"datetime": dt_str, "location": m_loc})
        save_data(data)
        await update.message.reply_text(f"✅ Матч назначен!\n📅 {m_date} | ⏰ {m_time}\n📍 {m_loc}")
    except ValueError:
        await update.message.reply_text("❌ Ошибка в формате даты/времени. Попробуйте снова через /match")
    
    context.user_data.clear()
    return ConversationHandler.END

async def matches_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data.get("matches"):
        await update.message.reply_text("Матчей пока не запланировано.")
        return

    lines = ["📅 **Расписание матчей:**"]
    # Сортировка по дате (упрощенная)
    for m in data["matches"]:
        lines.append(f"• {m['datetime']} — {m['location']}")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ==================== ЗАПУСК ====================
def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    match_conv = ConversationHandler(
        entry_points=[CommandHandler("match", match_start)],
        states={
            MATCH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_date)],
            MATCH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_time)],
            MATCH_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conv)
    app.add_handler(match_conv)
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("add_player", add_player))
    app.add_handler(CommandHandler("delete_player", delete_player))
    app.add_handler(CommandHandler("matches", matches_list))
    app.add_handler(CommandHandler("cancel", cancel))

    print("⚽️ Бот команды запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
