import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8330028687:AAEU9Qah_ykkUgA32Dw2ev9x1NVkNplrvs8"
DATA_FILE = "team.json"
COACH_ID = 7908057052  # Ваш ID

# ==================== РАБОТА С ФАЙЛОМ ====================
def load_team():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_team(team_list):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(team_list, f, ensure_ascii=False, indent=2)

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽️ **Управление составом:**\n\n"
        "/team — Посмотреть список игроков\n"
        "/add Имя Позиция — Добавить игрока\n"
        "/delete Номер — Удалить игрока по номеру"
    )

async def show_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    team = load_team()
    if not team:
        await update.message.reply_text("📋 Состав пуст.")
        return
    
    text = "🧑‍🤝‍🧑 **Текущий состав:**\n\n"
    for i, player in enumerate(team, 1):
        text += f"{i}. {player}\n"
    
    text += f"\nВсего: {len(team)}"
    await update.message.reply_text(text)

async def add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != COACH_ID:
        await update.message.reply_text("❌ Только тренер может добавлять игроков.")
        return

    if not context.args:
        await update.message.reply_text("Пример: `/add Иван Вратарь`", parse_mode="Markdown")
        return

    player_info = " ".join(context.args)
    team = load_team()
    team.append(player_info)
    save_team(team)
    
    await update.message.reply_text(f"✅ Добавлен: {player_info}")

async def delete_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != COACH_ID:
        return

    if not context.args:
        await update.message.reply_text("Пример: `/delete 1` (удалить первого в списке)", parse_mode="Markdown")
        return

    team = load_team()
    try:
        idx = int(context.args[0]) - 1
        if 0 <= idx < len(team):
            removed = team.pop(idx)
            save_team(team)
            await update.message.reply_text(f"🗑 Удален: {removed}")
        else:
            await update.message.reply_text("❌ Нет игрока под таким номером.")
    except ValueError:
        await update.message.reply_text("Введите число (номер игрока).")

# ==================== ЗАПУСК ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("team", show_team))
    app.add_handler(CommandHandler("add", add_player))
    app.add_handler(CommandHandler("delete", delete_player))

    print("🚀 Бот запущен. Команды: /team, /add, /delete")
    app.run_polling()

if __name__ == "__main__":
    main()
