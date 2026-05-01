import json
import logging
import uuid
import asyncio
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
# Токен вашого бота
BOT_TOKEN = "8439681853:AAHIo-WfoP9ZXgMwRjJHLDWpKPA6qLSFQC8"

DATA_FILE = "data.json"
MAX_PLAYERS = 7
REMINDER_HOURS_BEFORE = 2

# ID тренера (зафіксований)
FIXED_COACH_ID = 7908057052

# Состояния для ConversationHandler
PROFILE_NAME = 0
MATCH_DATE, MATCH_TIME, MATCH_LOCATION = range(1, 4)

# Список позицій
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
    team_list = data["team"]["players"]
    players_db = data["players"]
    if not team_list:
        return "Состав команды пуст."
    
    lines = []
    for idx, uid in enumerate(team_list, 1):
        p = players_db.get(str(uid), {})
        name = p.get("name", "Неизвестный")
        pos = p.get("position", "Позиция не назначена")
        lines.append(f"{idx}. {name} — {pos}")
    return "🧑‍🤝‍🧑 Текущий состав:\n" + "\n".join(lines)

def get_future_matches(data: dict) -> List[dict]:
    now = datetime.now()
    future = []
    for m in data["matches"]:
        try:
            if datetime.fromisoformat(m["datetime"]) > now:
                future.append(m)
        except ValueError:
            continue
    future.sort(key=lambda m: m["datetime"])
    return future

def format_match(match: dict) -> str:
    dt = datetime.fromisoformat(match["datetime"]).strftime("%d.%m.%Y %H:%M")
    return (
        f"📅 Дата: {dt}\n"
        f"📍 Место: {match['location']}"
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
        "/profile — создать или посмотреть свой профиль\n"
        "/team — посмотреть текущий состав команды\n"
        "/matches — список будущих матчей\n\n"
        "🔧 Команды для тренера:\n"
        "/add_player @user — добавить игрока по нику\n"
        "/add_player Имя Позиция — добавить игрока вручную\n"
        "/setplayer @ник Позиция — назначить позицию игроку\n"
        "/match — запланировать новый матч\n"
        "/setcoach @ник — передать права тренера (если не зафиксирован)\n\n"
        f"Доступные позиции: {', '.join(POSITIONS)}"
    )
    await update.message.reply_text(help_text)

# -------------------- ПРОФИЛЬ --------------------
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    if str(user_id) in data["players"]:
        p = data["players"][str(user_id)]
        text = (
            f"👤 Ваш профиль:\n"
            f"Имя: {p['name']}\n"
            f"Позиция: {p.get('position') or 'не назначена'}\n"
            f"Контакт: @{p['contact']}"
        )
        await update.message.reply_text(text)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Введите ваше имя или игровой никнейм:")
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
    
    await update.message.reply_text(
        f"✅ Профиль сохранён, {name}!\n"
        "Теперь тренер может добавить вас в команду и назначить позицию.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def profile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# -------------------- УПРАВЛЕНИЕ ИГРОКАМИ --------------------
async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ У вас нет прав тренера для выполнения этой команды.")
        return

    if not context.args:
        await update.message.reply_text(
            "Использование:\n"
            "/add_player @username\n"
            "/add_player Имя Позиция"
        )
        return

    # Если команда пуста, инициализируем тренера
    if not data["team"]["players"]:
        if str(user_id) not in data["players"]:
            await update.message.reply_text("Сначала создайте свой профиль через /profile")
            return
        data["team"]["players"].append(user_id)
        data["team"]["coach"] = FIXED_COACH_ID or user_id
        save_data(data)

    arg = context.args[0]
    if arg.startswith("@"):
        username = arg.lstrip("@")
        target_id = None
        for uid, p in data["players"].items():
            if p.get("contact") == username:
                target_id = uid
                break
        
        if not target_id:
            await update.message.reply_text(f"Игрок @{username} не найден. Он должен сначала вызвать /profile.")
            return
            
        if target_id in data["team"]["players"] or int(target_id) in data["team"]["players"]:
            await update.message.reply_text("Этот игрок уже в составе.")
            return

        if len(data["team"]["players"]) >= MAX_PLAYERS:
            await update.message.reply_text(f"Достигнут лимит игроков ({MAX_PLAYERS}).")
            return

        data["team"]["players"].append(int(target_id))
        save_data(data)
        await update.message.reply_text(f"✅ @{username} добавлен в команду.")
    else:
        if len(context.args) < 2:
            await update.message.reply_text("Для ручного добавления введите: /add_player Имя Позиция")
            return
        
        name = context.args[0]
        position = " ".join(context.args[1:])
        
        if position not in POSITIONS:
            await update.message.reply_text(f"Ошибка. Выберите позицию из списка: {', '.join(POSITIONS)}")
            return

        if len(data["team"]["players"]) >= MAX_PLAYERS:
            await update.message.reply_text("Лимит команды исчерпан.")
            return

        manual_id = f"manual_{uuid.uuid4().hex[:8]}"
        data["players"][manual_id] = {
            "name": name,
            "position": position,
            "contact": None
        }
        data["team"]["players"].append(manual_id)
        save_data(data)
        await update.message.reply_text(f"✅ Игрок {name} добавлен вручную на позицию {position}.")

async def setplayer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    
    if not is_coach(user_id, data):
        await update.message.reply_text("❌ Только тренер может менять позиции.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Формат: /setplayer @ник Позиция или /setplayer Имя Позиция")
        return

    target_input = context.args[0]
    new_pos = " ".join(context.args[1:])

    if new_pos not in POSITIONS:
        await update.message.reply_text(f"Недопустимая позиция. Список: {', '.join(POSITIONS)}")
        return

    target_uid = None
    if target_input.startswith("@"):
        uname = target_input.lstrip("@")
        for uid, p in data["players"].items():
            if p.get("contact") == uname:
                target_uid = uid
                break
    else:
        target_uid = find_player_by_name(data, target_input)

    if not target_uid:
        await update.message.reply_text("Игрок не найден.")
        return

    data["players"][str(target_uid)]["position"] = new_pos
    save_data(data)
    await update.message.reply_text(f"✅ Позиция для {target_input} изменена на {new_pos}.")

# -------------------- МАТЧИ И СОСТАВ --------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    text = get_team_display(data)
    coach_id = FIXED_COACH_ID or data["team"]["coach"]
    if coach_id:
        p = data["players"].get(str(coach_id), {})
        c_name = p.get("name", "Не назначен")
        text += f"\n\n📋 Тренер: {c_name}"
    await update.message.reply_text(text)

async def match_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_coach(user_id, load_data()):
        await update.message.reply_text("❌ Только тренер может создавать матчи.")
        return ConversationHandler.END
    await update.message.reply_text("Введите дату матча (ДД.ММ.ГГГГ):")
    return MATCH_DATE

async def match_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%d.%m.%Y")
        context.user_data["m_date"] = text
        await update.message.reply_text("Введите время (ЧЧ:ММ):")
        return MATCH_TIME
    except ValueError:
        await update.message.reply_text("Неверный формат. Нужно ДД.ММ.ГГГГ (например, 15.05.2026):")
        return MATCH_DATE

async def match_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%H:%M")
        context.user_data["m_time"] = text
        await update.message.reply_text("Введите место проведения:")
        return MATCH_LOCATION
    except ValueError:
        await update.message.reply_text("Неверный формат. Нужно ЧЧ:ММ (например, 19:00):")
        return MATCH_TIME

async def match_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.text.strip()
    m_date = context.user_data["m_date"]
    m_time = context.user_data["m_time"]
    
    full_dt = f"{m_date} {m_time}"
    dt_obj = datetime.strptime(full_dt, "%d.%m.%Y %H:%M")
    
    data = load_data()
    new_match = {
        "datetime": dt_obj.isoformat(),
        "location": loc
    }
    data["matches"].append(new_match)
    save_data(data)
    
    await update.message.reply_text(f"✅ Матч успешно запланирован!\n{format_match(new_match)}")
    return ConversationHandler.END

async def matches_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    future = get_future_matches(data)
    if not future:
        await update.message.reply_text("Предстоящих матчей пока нет.")
        return
    
    res = ["<b>Расписание матчей:</b>"]
    for i, m in enumerate(future, 1):
        res.append(f"\n{i}. {format_match(m)}")
    
    await update.message.reply_text("\n".join(res), parse_mode="HTML")

async def setcoach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if FIXED_COACH_ID:
        await update.message.reply_text("❌ В этом боте тренер жестко задан в коде.")
        return
    # Логика смены тренера, если FIXED_COACH_ID был бы None
    await update.message.reply_text("Смена тренера недоступна, так как ID зафиксирован.")

# ==================== ФОНОВЫЕ ЗАДАЧИ ====================
async def check_matches_callback(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = datetime.now()
    coach_id = FIXED_COACH_ID or data["team"]["coach"]
    
    if not coach_id:
        return

    for m in data["matches"]:
        m_dt = datetime.fromisoformat(m["datetime"])
        # Проверяем, если до матча осталось меньше заданного времени
        if now < m_dt <= now + timedelta(hours=REMINDER_HOURS_BEFORE):
            # Простая логика, чтобы не спамить (в реальности нужен флаг 'notified')
            try:
                await context.bot.send_message(
                    chat_id=coach_id,
                    text=f"🔔 Напоминание для тренера!\nМатч скоро начнется:\n{format_match(m)}"
                )
            except Exception:
                pass

# ==================== ЗАПУСК ====================
def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )

    app = Application.builder().token(BOT_TOKEN).build()

    # Сценарий профиля
    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("profile", profile_start)],
        states={
            PROFILE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)],
        },
        fallbacks=[CommandHandler("cancel", profile_cancel)],
    )

    # Сценарий матча
    match_conv = ConversationHandler(
        entry_points=[CommandHandler("match", match_start)],
        states={
            MATCH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_date)],
            MATCH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_time)],
            MATCH_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_location)],
        },
        fallbacks=[CommandHandler("cancel", profile_cancel)],
    )

    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(profile_conv)
    app.add_handler(match_conv)
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("add_player", add_player))
    app.add_handler(CommandHandler("setplayer", setplayer))
    app.add_handler(CommandHandler("matches", matches_list))
    app.add_handler(CommandHandler("setcoach", setcoach))

    # Очередь задач (напоминания)
    if app.job_queue:
        app.job_queue.run_repeating(check_matches_callback, interval=1800, first=10)

    print("Бот запущен и готов к работе...")
    app.run_polling()

if __name__ == "__main__":
    main()
