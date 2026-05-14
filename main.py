import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# --- КОНФИГУРАЦИЯ ---
TOKEN = '8330028687:AAEU9Qah_ykkUgA32Dw2ev9x1NVkNplrvs8'
ADMINS = [5274130061, 7908057052]

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('football_manager.db')
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, username TEXT, club_name TEXT, budget INTEGER, reg_date TEXT)''')
    # Таблица игроков
    cursor.execute('''CREATE TABLE IF NOT EXISTS players 
                      (player_id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, 
                       position TEXT, age INTEGER, salary INTEGER, status TEXT, last_retired TEXT)''')
    
    # Наполняем рынок, если он пуст
    cursor.execute("SELECT COUNT(*) FROM players")
    if cursor.fetchone()[0] == 0:
        market_players = [
            (0, 'Криштиану Роналду', 'Нападающий', 39, 900000, 'free'),
            (0, 'Килиан Мбаппе', 'Нападающий', 25, 1500000, 'free'),
            (0, 'Джуд Беллингем', 'Полузащитник', 20, 1100000, 'free'),
            (0, 'Винисиус Жуниор', 'Нападающий', 23, 1300000, 'free'),
            (0, 'Ламин Ямаль', 'Вингер', 16, 700000, 'free')
        ]
        cursor.executemany("INSERT INTO players (owner_id, name, position, age, salary, status) VALUES (?,?,?,?,?,?)", market_players)
    
    conn.commit()
    conn.close()

# --- СОСТОЯНИЯ РЕГИСТРАЦИИ ---
CLUB_NAME = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('football_manager.db')
    cursor = conn.cursor()
    cursor.execute("SELECT club_name, budget FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        await update.message.reply_text(
            f"🏟 **Клуб:** «{user[0]}»\n💰 **Бюджет:** {user[1]:,} €\n\n"
            "**Управление:**\n"
            "/my_players — Состав клуба\n"
            "/free_agents — Рынок игроков\n"
            "/admin_money — Получить 50 млн (только для админов)"
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("⚽ Добро пожаловать! Как будет называться ваш клуб?")
        return CLUB_NAME

async def register_club(update: Update, context: ContextTypes.DEFAULT_TYPE):
    club_name = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Тренер"
    
    conn = sqlite3.connect('football_manager.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                   (user_id, username, club_name, 100000000, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Клуб «{club_name}» успешно создан!\nНапишите /start, чтобы открыть меню.")
    return ConversationHandler.END

# --- ФУНКЦИИ ИГРОКОВ ---

async def free_agents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('football_manager.db')
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, name, position, salary FROM players WHERE status = 'free'")
    players = cursor.fetchall()
    conn.close()

    if not players:
        await update.message.reply_text("На рынке сейчас нет игроков.")
        return

    keyboard = [[InlineKeyboardButton(f"✍️ {p[1]} | {p[3]:,} €", callback_data=f"sign_{p[0]}")] for p in players]
    await update.message.reply_text("📋 Свободные агенты:", reply_markup=InlineKeyboardMarkup(keyboard))

async def my_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('football_manager.db')
    cursor = conn.cursor()
    cursor.execute("SELECT player_id, name, position FROM players WHERE owner_id = ? AND status = 'active'", (user_id,))
    players = cursor.fetchall()
    conn.close()

    if not players:
        await update.message.reply_text("В вашем клубе пока нет игроков. Купите их в /free_agents")
        return

    keyboard = [[InlineKeyboardButton(f"👞 Завершить карьеру: {p[1]}", callback_data=f"retire_{p[0]}")] for p in players]
    await update.message.reply_text("🏃 Ваш текущий состав:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- ОБРАБОТКА CALLBACK ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    conn = sqlite3.connect('football_manager.db')
    cursor = conn.cursor()

    if data.startswith("sign_"):
        p_id = data.split("_")[1]
        cursor.execute("SELECT budget FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if not res: return
        
        budget = res[0]
        cursor.execute("SELECT name, salary FROM players WHERE player_id = ?", (p_id,))
        p_name, p_salary = cursor.fetchone()

        if budget >= p_salary:
            cursor.execute("UPDATE users SET budget = budget - ? WHERE user_id = ?", (p_salary, user_id))
            cursor.execute("UPDATE players SET owner_id = ?, status = 'active' WHERE player_id = ?", (user_id, p_id))
            conn.commit()
            await query.edit_message_text(f"🤝 Контракт подписан! {p_name} перешел в ваш клуб.")
        else:
            await query.answer("❌ Недостаточно средств!", show_alert=True)

    elif data.startswith("retire_"):
        p_id = data.split("_")[1]
        now = datetime.now()
        cursor.execute("SELECT name, last_retired FROM players WHERE player_id = ?", (p_id,))
        p_name, last_ret = cursor.fetchone()

        # Проверка КД 7 дней
        if last_ret:
            last_date = datetime.strptime(last_ret, "%Y-%m-%d %H:%M:%S")
            if now < last_date + timedelta(days=7):
                await query.answer("⏳ Нельзя завершать карьеру чаще, чем раз в неделю!", show_alert=True)
                conn.close()
                return

        cursor.execute("UPDATE players SET status = 'retired', owner_id = 0, last_retired = ? WHERE player_id = ?", 
                       (now.strftime("%Y-%m-%d %H:%M:%S"), p_id))
        conn.commit()
        await query.edit_message_text(f"👞 {p_name} завершил профессиональную карьеру.")

    conn.close()

# --- АДМИН-КОМАНДА ---
async def admin_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("⛔ Эта команда доступна только администраторам.")
        return
        
    conn = sqlite3.connect('football_manager.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET budget = budget + 50000000 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("💰 Читы сработали! +50.000.000 € зачислено.")

# --- ЗАПУСК ---
def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    # Обработчик регистрации
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

    print("✅ Бот запущен! Ожидание сообщений...")
    application.run_polling()

if __name__ == '__main__':
    main()
