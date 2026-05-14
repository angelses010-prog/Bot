import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationAdapter

# --- КОНФИГУРАЦИЯ ---
TOKEN = '8330028687:AAEU9Qah_ykkUgA32Dw2ev9x1NVkNplrvs8'
ADMIN_ID = 5274130061

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('fm_bot.db')
    cursor = conn.cursor()
    # Таблица менеджеров
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, username TEXT, club_name TEXT, budget INTEGER, reg_date TEXT)''')
    # Таблица футболистов
    cursor.execute('''CREATE TABLE IF NOT EXISTS players 
                      (player_id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, 
                       position TEXT, age INTEGER, salary INTEGER, status TEXT, last_retired TEXT)''')
    
    # Стартовый набор футболистов на рынок
    cursor.execute("SELECT COUNT(*) FROM players")
    if cursor.fetchone()[0] == 0:
        initial_players = [
            (0, 'Криштиану Роналду', 'Нападающий', 39, 900000, 'free'),
            (0, 'Килиан Мбаппе', 'Нападающий', 25, 1500000, 'free'),
            (0, 'Джуд Беллингем', 'Полузащитник', 20, 1100000, 'free'),
            (0, 'Винисиус Жуниор', 'Нападающий', 23, 1300000, 'free')
        ]
        cursor.executemany("INSERT INTO players (owner_id, name, position, age, salary, status) VALUES (?,?,?,?,?,?)", initial_players)
    
    conn.commit()
    conn.close()

# --- ЛОГИКА РЕГИСТРАЦИИ ---
CLUB_NAME = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('fm_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT club_name, budget FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        await update.message.reply_text(
            f"🏟 Клуб: «{user[0]}»\n💰 Бюджет: {user[1]:,} €\n\n"
            "Команды:\n"
            "/my_players — Мой состав и завершение карьеры\n"
            "/free_agents — Рынок свободных агентов\n"
            "/recruit — Создать объявление о наборе"
        )
        return ConversationAdapter.END
    else:
        await update.message.reply_text("⚽ Добро пожаловать в футбольный менеджер!\nВведите название вашего будущего клуба:")
        return CLUB_NAME

async def register_club(update: Update, context: ContextTypes.DEFAULT_TYPE):
    club_name = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Тренер"
    
    conn = sqlite3.connect('fm_bot.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                       (user_id, username, club_name, 100000000, datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        await update.message.reply_text(f"✅ Клуб «{club_name}» успешно создан!\n💰 Вам выделено: 100 000 000 €\nИспользуйте /start для входа.")
    except Exception as e:
        await update.message.reply_text("Произошла ошибка при регистрации.")
    finally:
        conn.close()
    return ConversationAdapter.END

# --- РЫНОК И СОСТАВ ---

async def free_agents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('fm_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, name, position, salary FROM players WHERE status = 'free'")
    players = cursor.fetchall()
    conn.close()

    if not players:
        await update.message.reply_text("На рынке пока нет свободных агентов.")
        return

    keyboard = [[InlineKeyboardButton(f"✍️ {p[1]} | {p[3]:,}€", callback_data=f"sign_{p[0]}")] for p in players]
    await update.message.reply_text("📋 Свободные агенты (нажми, чтобы подписать):", reply_markup=InlineKeyboardMarkup(keyboard))

async def my_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('fm_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, name, position FROM players WHERE owner_id = ? AND status = 'active'", (user_id,))
    players = cursor.fetchall()
    conn.close()

    if not players:
        await update.message.reply_text("Ваш состав пуст. Загляните в /free_agents")
        return

    keyboard = [[InlineKeyboardButton(f"👞 Завершить карьеру: {p[1]}", callback_data=f"retire_{p[0]}")] for p in players]
    await update.message.reply_text("🏃 Ваши игроки:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- ОБРАБОТКА ДЕЙСТВИЙ ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    conn = sqlite3.connect('fm_bot.db')
    cursor = conn.cursor()

    if data.startswith("sign_"):
        p_id = data.split("_")[1]
        cursor.execute("SELECT budget FROM users WHERE user_id = ?", (user_id,))
        budget = cursor.fetchone()[0]
        cursor.execute("SELECT name, salary FROM players WHERE player_id = ?", (p_id,))
        p_name, p_salary = cursor.fetchone()

        if budget >= p_salary:
            cursor.execute("UPDATE users SET budget = budget - ? WHERE user_id = ?", (p_salary, user_id))
            cursor.execute("UPDATE players SET owner_id = ?, status = 'active' WHERE player_id = ?", (user_id, p_id))
            conn.commit()
            await query.edit_message_text(f"🤝 Поздравляем! {p_name} теперь в вашем клубе!")
        else:
            await query.answer("❌ Недостаточно средств в бюджете!", show_alert=True)

    elif data.startswith("retire_"):
        p_id = data.split("_")[1]
        now = datetime.now()
        cursor.execute("SELECT name, last_retired FROM players WHERE player_id = ?", (p_id,))
        p_name, last_ret = cursor.fetchone()

        # КД 7 дней
        if last_ret:
            last_date = datetime.strptime(last_ret, "%Y-%m-%d %H:%M:%S")
            if now < last_date + timedelta(days=7):
                diff = (last_date + timedelta(days=7)) - now
                await query.answer(f"⏳ Кулдаун! Ждите {diff.days} дн.", show_alert=True)
                conn.close()
                return

        cursor.execute("UPDATE players SET status = 'retired', last_retired = ? WHERE player_id = ?", 
                       (now.strftime("%Y-%m-%d %H:%M:%S"), p_id))
        conn.commit()
        await query.edit_message_text(f"👞 {p_name} повесил бутсы на гвоздь.")

    conn.close()

# --- АДМИНКА ---
async def admin_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('fm_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET budget = budget + 50000000 WHERE user_id = ?", (user_id,)) # Использует твой ID
    conn.commit()
    conn.close()
    await update.message.reply_text("💰 Админ-бонус +50.000.000 € зачислен!")

# --- ЗАПУСК ---
def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    reg_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={CLUB_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_club)]},
        fallbacks=[]
    )

    application.add_handler(reg_handler)
    application.add_handler(CommandHandler('free_agents', free_agents))
    application.add_handler(CommandHandler('my_players', my_players))
    application.add_handler(CommandHandler('admin_money', admin_money))
    application.add_handler(CallbackQueryHandler(handle_callback))

    print("✅ Бот запущен. Напиши /start в Telegram.")
    application.run_polling()

if __name__ == '__main__':
    main()
