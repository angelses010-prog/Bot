import json
import logging
import uuid
import os
from datetime import datetime, timedelta
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
BOT_TOKEN = os.getenv("8439681853:AAHIo-WfoP9ZXgMwRjJHLDWpKPA6qLSFQC8"
)

if not BOT_TOKEN:
    raise ValueError("❌ Укажи BOT_TOKEN через переменную окружения")

DATA_FILE = "data.json"
MAX_PLAYERS = 7
REMINDER_HOURS_BEFORE = 2

FIXED_COACH_ID = 7908057052  # ID тренера

PROFILE_NAME = 0
MATCH_DATE, MATCH_TIME, MATCH_LOCATION = range(3)

POSITIONS = [
    "Вратарь",
    "Правый Защитник",
    "Левый Защитник",
    "Полузащитник",
    "Правый Вингер",
    "Центральный Нападающий",
    "Левый Вингер"
]

# ==================== РАБОТА С ДАННЫМИ ====================
def load_data() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"players": {}, "team": {"players": [], "coach": None}, "matches": []}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_coach(user_id: int, data: dict) -> bool:
    if FIXED_COACH_ID is not None:
        return user_id == FIXED_COACH_ID
    return data["team"]["coach"] == user_id

def get_team_display(data: dict) -> str:
    team = data["team"]["players"]
    players = data["players"]
    if not team:
        return "Состав команды пуст."
    lines = []
    for idx, uid in enumerate(team, 1):
        p = players.get(str(uid), {})
        name = p.get("name", "Неизвестный")
        pos = p.get("position", "?")
        lines.append(f"{idx}. {name} – {pos}")
    return "🧑‍🤝‍🧑 Текущий состав:\n" + "\n".join(lines)

def get_future_matches(data: dict) -> List[dict]:
    now = datetime.now()
    future = [m for m in data["matches"] if datetime.fromisoformat(m["datetime"]) > now]
    future.sort(key=lambda m: m["datetime"])
    return future

def format_match(match: dict) -> str:
    dt = datetime.fromisoformat(match["datetime"]).strftime("%d.%m.%Y %H:%M")
    return (
        f"📅 {dt}\n"
        f"📍 {match['location']}"
    )

def find_player_by_name(data: dict, name: str) -> Optional[str]:
    for uid, p in data["players"].items():
        if p.get("name") == name:
            return uid
    return None

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "⚽️ Бот мини-футбольной команды\n\n"
        "Доступные команды:\n"
        "/profile — создать/посмотреть профиль\n"
        "/team — состав команды\n"
        "/add_player @user или Имя Позиция\n"
        "/match — создать матч\n"
        "/matches — список матчей\n"
        "/setplayer — назначить позицию\n"
    )
    await update.message.reply_text(help_text)

# -------------------- ПРОФИЛЬ --------------------
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    if str(user_id) in data["players"]:
        p = data["players"][str(user_id)]
        text = (
            f"Имя: {p['name']}\n"
            f"Позиция: {p.get('position')}\n"
            f"Контакт: @{p['contact']}"
        )
        await update.message.reply_text(text)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Введите имя:")
        return PROFILE_NAME

async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user = update.effective_user
    data = load_data()

    data["players"][str(user.id)] = {
        "name": name,
        "position": None,
        "contact": user.username or f"id{user.id}"
    }

    save_data(data)

    await update.message.reply_text("Профиль создан ✅")
    return ConversationHandler.END

# -------------------- ДОБАВЛЕНИЕ --------------------
async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()

    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Только тренер")
        return

    if not context.args:
        await update.message.reply_text("Пример: /add_player Имя Позиция")
        return

    if len(data["team"]["players"]) >= MAX_PLAYERS:
        await update.message.reply_text("Команда заполнена")
        return

    name = context.args[0]
    pos = " ".join(context.args[1:])

    new_id = f"manual_{uuid.uuid4().hex[:6]}"

    data["players"][new_id] = {
        "name": name,
        "position": pos,
        "contact": None
    }

    data["team"]["players"].append(new_id)
    save_data(data)

    await update.message.reply_text(f"{name} добавлен")

# -------------------- НАЗНАЧЕНИЕ ПОЗИЦИИ --------------------
async def setplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    if not is_coach(update.effective_user.id, data):
        await update.message.reply_text("❌ Только тренер")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Пример: /setplayer Имя Позиция")
        return

    name = context.args[0]
    pos = " ".join(context.args[1:])

    uid = find_player_by_name(data, name)

    if not uid:
        await update.message.reply_text("Игрок не найден")
        return

    data["players"][uid]["position"] = pos
    save_data(data)

    await update.message.reply_text("Обновлено ✅")

# -------------------- СОСТАВ --------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    await update.message.reply_text(get_team_display(data))

# -------------------- МАТЧ --------------------
async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Дата ДД.ММ.ГГГГ")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text
    await update.message.reply_text("Время ЧЧ:ММ")
    return MATCH_TIME

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time"] = update.message.text
    await update.message.reply_text("Локация")
    return MATCH_LOCATION

async def match_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    dt = datetime.strptime(
        f"{context.user_data['date']} {context.user_data['time']}",
        "%d.%m.%Y %H:%M"
    )

    data["matches"].append({
        "datetime": dt.isoformat(),
        "location": update.message.text,
        "participants": {}
    })

    save_data(data)

    await update.message.reply_text("Матч создан ✅")
    return ConversationHandler.END

# -------------------- СПИСОК --------------------
async def matches_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    future = get_future_matches(data)

    if not future:
        await update.message.reply_text("Нет матчей")
        return

    text = "\n\n".join([format_match(m) for m in future])
    await update.message.reply_text(text)

# -------------------- УВЕДОМЛЕНИЯ --------------------
async def check_matches_callback(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()

    for match in data["matches"]:
        dt = datetime.fromisoformat(match["datetime"])

        if now + timedelta(hours=REMINDER_HOURS_BEFORE) >= dt > now:
            coach_id = FIXED_COACH_ID
            try:
                await context.bot.send_message(
                    chat_id=coach_id,
                    text=f"⏰ Скоро матч!\n{format_match(match)}"
                )
            except Exception as e:
                logging.warning(e)

# ==================== MAIN ====================
def main():
    logging.basicConfig(level=logging.INFO)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("add_player", add_player))
    app.add_handler(CommandHandler("matches", matches_list))
    app.add_handler(CommandHandler("setplayer", setplayer))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)]},
        fallbacks=[]
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("match", match_start)],
        states={
            MATCH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_date)],
            MATCH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_time)],
            MATCH_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_location)],
        },
        fallbacks=[]
    ))

    app.job_queue.run_repeating(check_matches_callback, interval=600, first=10)

    print("🚀 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
