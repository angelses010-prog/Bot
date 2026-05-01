import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Важливо: python-telegram-bot використовує назву 'telegram' для імпорту
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
MAX_PLAYERS = 7
REMINDER_HOURS_BEFORE = 2

FIXED_COACH_ID = 7908057052  # ID тренера

PROFILE_NAME = 0
MATCH_DATE, MATCH_TIME, MATCH_LOCATION = range(1, 4)

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
            content = f.read()
            if not content:
                return {"players": {}, "team": {"players": [], "coach": None}, "matches": []}
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
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
    future = []
    for m in data.get("matches", []):
        try:
            if datetime.fromisoformat(m["datetime"]) > now:
                future.append(m)
        except:
            continue
    future.sort(key=lambda m: m["datetime"])
    return future

def format_match(match: dict) -> str:
    dt = datetime.fromisoformat(match["datetime"]).strftime("%d.%m.%Y %H:%M")
    return f"📅 {dt}\n📍 {match['location']}"

def find_player_by_name(data: dict, name: str) -> Optional[str]:
    for uid, p in data["players"].items():
        if p.get("name") == name:
            return uid
    return None

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "⚽️ Бот мини-футбольной команды\n\n"
        "Команды:\n"
        "/profile — создать/посмотреть профиль\n"
        "/team — состав команды\n"
        "/matches — список будущих матчей\n\n"
        "Тренер:\n"
        "/add_player @user — добавить игрока\n"
        "/add_player Имя Позиция — добавить вручную\n"
        "/setplayer @name Позиция — изменить позицию\n"
        "/match — создать матч\n"
        f"Позиции: {', '.join(POSITIONS)}"
    )
    await update.message.reply_text(help_text)

async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    if str(user_id) in data["players"]:
        p = data["players"][str(user_id)]
        text = f"Ваш профиль:\nИмя: {p['name']}\nПозиция: {p.get('position') or 'не назначена'}\nКонтакт: @{p['contact']}"
        await update.message.reply_text(text)
        return ConversationHandler.END
    await update.message.reply_text("Введите ваше имя:")
    return PROFILE_NAME

async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    user = update.effective_user
    data = load_data()
    data["players"][str(user.id)] = {"name": name, "position": None, "contact": user.username or f"id{user.id}"}
    save_data(data)
    await update.message.reply_text("✅ Профиль сохранён!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Доступ только для тренера.")
        return
    
    if not context.args:
        await update.message.reply_text("Пример: /add_player @username або /add_player Имя Позиция")
        return

    # Логика добавления...
    arg = context.args[0]
    if arg.startswith("@"):
        username = arg.lstrip("@")
        target_id = next((uid for uid, p in data["players"].items() if p.get("contact") == username), None)
        if not target_id:
            await update.message.reply_text("Игрок не найден. Пусть он нажмет /profile")
            return
        if int(target_id) not in data["team"]["players"]:
            data["team"]["players"].append(int(target_id))
            save_data(data)
            await update.message.reply_text(f"✅ @{username} добавлен в команду.")
    else:
        # Ручное добавление
        if len(context.args) < 2: return
        name, pos = context.args[0], " ".join(context.args[1:])
        new_id = f"manual_{uuid.uuid4().hex[:8]}"
        data["players"][new_id] = {"name": name, "position": pos, "contact": None}
        data["team"]["players"].append(new_id)
        save_data(data)
        await update.message.reply_text(f"✅ {name} добавлен!")

async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_team_display(load_data()))

async def matches_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    future = get_future_matches(load_data())
    if not future:
        await update.message.reply_text("Нет матчей.")
        return
    text = "📋 Матчи:\n" + "\n".join([format_match(m) for m in future])
    await update.message.reply_text(text)

async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id, load_data()): return ConversationHandler.END
    await update.message.reply_text("Дата (ДД.ММ.ГГГГ):")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_date"] = update.message.text
    await update.message.reply_text("Время (ЧЧ:ММ):")
    return MATCH_TIME

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_time"] = update.message.text
    await update.message.reply_text("Место:")
    return MATCH_LOCATION

async def match_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    dt_str = f"{context.user_data['m_date']} {context.user_data['m_time']}"
    try:
        dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        data["matches"].append({"datetime": dt.isoformat(), "location": update.message.text})
        save_data(data)
        await update.message.reply_text("✅ Матч создан!")
    except:
        await update.message.reply_text("Ошибка в дате.")
    return ConversationHandler.END

def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("matches", matches_list))
    app.add_handler(CommandHandler("add_player", add_player))
    
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

    print("🚀 Запуск...")
    app.run_polling()

if __name__ == "__main__":
    main()
