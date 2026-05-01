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
MAX_PLAYERS = 7

FIXED_COACH_ID = 7908057052  # ID тренера

# Состояния для диалогов
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
    return user_id == FIXED_COACH_ID

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "⚽️ Бот управления командой\n\n"
        "Команды для всех:\n"
        "/profile — создать свой профиль\n"
        "/team — посмотреть состав\n"
        "/matches — расписание матчей\n\n"
        "Команды для тренера:\n"
        "/add_player @user — добавить игрока по нику\n"
        "/add_player Имя Позиция — добавить вручную\n"
        "/delete_player — удалить игрока из состава\n"
        "/match — создать новый матч\n"
        "/cancel — отмена любого процесса ввода"
    )
    await update.message.reply_text(help_text)

# -------------------- УПРАВЛЕНИЕ СОСТАВОМ --------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    team_list = data["team"]["players"]
    players = data["players"]
    
    if not team_list:
        await update.message.reply_text("Состав пуст.")
        return

    lines = ["🧑‍🤝‍🧑 **Текущий состав:**"]
    for idx, uid in enumerate(team_list, 1):
        p = players.get(str(uid), {})
        name = p.get("name", "Неизвестный")
        pos = p.get("position", "Позиция не задана")
        lines.append(f"{idx}. {name} — {pos}")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Только тренер может добавлять игроков.")
        return

    if not context.args:
        await update.message.reply_text("Использование:\n/add_player @username\n/add_player Имя Позиция")
        return

    if len(data["team"]["players"]) >= MAX_PLAYERS:
        await update.message.reply_text(f"Лимит {MAX_PLAYERS} игроков исчерпан.")
        return

    arg = context.args[0]
    if arg.startswith("@"):
        username = arg.lstrip("@")
        target_id = None
        for uid, p in data["players"].items():
            if p.get("contact") == username:
                target_id = uid
                break
        
        if not target_id:
            await update.message.reply_text("Игрок не найден. Он должен сначала нажать /profile")
            return
        
        if target_id in data["team"]["players"] or (target_id.isdigit() and int(target_id) in data["team"]["players"]):
            await update.message.reply_text("Игрок уже в составе.")
            return

        uid_to_add = int(target_id) if target_id.isdigit() else target_id
        data["team"]["players"].append(uid_to_add)
        save_data(data)
        await update.message.reply_text(f"✅ @{username} добавлен в состав.")
    else:
        if len(context.args) < 2:
            await update.message.reply_text("Укажите позицию. Пример: /add_player Иван Вратарь")
            return
        
        name = context.args[0]
        pos = " ".join(context.args[1:])
        manual_id = f"manual_{uuid.uuid4().hex[:8]}"
        
        data["players"][manual_id] = {"name": name, "position": pos, "contact": None}
        data["team"]["players"].append(manual_id)
        save_data(data)
        await update.message.reply_text(f"✅ Игрок {name} добавлен вручную.")

async def delete_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Только тренер может удалять игроков.")
        return

    if not context.args:
        await update.message.reply_text("Введите номер игрока из списка /team.\nПример: /delete_player 1")
        return

    try:
        idx = int(context.args[0]) - 1
        if 0 <= idx < len(data["team"]["players"]):
            removed_id = data["team"]["players"].pop(idx)
            save_data(data)
            await update.message.reply_text("✅ Игрок удален из состава.")
        else:
            await update.message.reply_text("Неверный номер.")
    except ValueError:
        await update.message.reply_text("Введите число (номер игрока).")

# -------------------- ПРОФИЛЬ --------------------
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = str(update.effective_user.id)
    if user_id in data["players"]:
        p = data["players"][user_id]
        await update.message.reply_text(f"Ваш профиль:\nИмя: {p['name']}\nКонтакт: @{p['contact']}")
        return ConversationHandler.END
    await update.message.reply_text("Введите ваше имя для профиля:")
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
    await update.message.reply_text(f"✅ Профиль {name} создан!")
    return ConversationHandler.END

# -------------------- МАТЧИ --------------------
async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_coach(update.effective_user.id, load_data()):
        await update.message.reply_text("❌ Только тренер создает матчи.")
        return ConversationHandler.END
    await update.message.reply_text("Введите дату матча (например, 15.05.2026):")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_date"] = update.message.text.strip()
    await update.message.reply_text("Введите время (например, 19:00):")
    return MATCH_TIME

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m_time"] = update.message.text.strip()
    await update.message.reply_text("Введите место проведения:")
    return MATCH_LOCATION

async def match_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    m_date = context.user_data.get("m_date")
    m_time = context.user_data.get("m_time")
    m_loc = update.message.text.strip()
    
    try:
        dt_str = f"{m_date} {m_time}"
        dt = datetime.strptime(dt_str, "%d.%m.%Y %H:%M")
        data["matches"].append({"datetime": dt.isoformat(), "location": m_loc})
        save_data(data)
        await update.message.reply_text(f"✅ Матч создан!\n📅 {m_date} в {m_time}\n📍 {m_loc}")
    except Exception as e:
        await update.message.reply_text("Ошибка в формате даты или времени. Используйте ДД.ММ.ГГГГ и ЧЧ:ММ")
    
    context.user_data.clear()
    return ConversationHandler.END

async def matches_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    future = [m for m in data.get("matches", []) if datetime.fromisoformat(m["datetime"]) > now]
    
    if not future:
        await update.message.reply_text("Нет предстоящих матчей.")
        return

    lines = ["📋 **Ближайшие матчи:**"]
    for m in sorted(future, key=lambda x: x["datetime"]):
        dt = datetime.fromisoformat(m["datetime"]).strftime("%d.%m.%Y %H:%M")
        lines.append(f"• {dt} — {m['location']}")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ==================== ЗАПУСК ====================
def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()

    # Сценарий профиля
    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Сценарий матча
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

    print("🚀 Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
