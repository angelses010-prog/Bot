import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- НАСТРОЙКИ ---
TOKEN = '8067572893:AAH0Lx_Dq2lENkuTDoHQO1v46NTe8WLWEpo'

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# --- ОБРАБОТЧИКИ КОМАНД ---

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        " Всем привет, от Лиги 1 @liga1slsfc и её Кубка @FFF_SLS.\n\n"
        " Чтобы попасть в Лигу, напишите @Verybigsun.\n\n"
        " Используйте /Page1 и /Page2, чтобы узнать про нас!"
    )
    await update.message.reply_text(text)

# Команда /Page1
async def page1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏆 **Page 1**\n\n"
        "Мы перспективная лига с относительно сильными клубами, "
        "в которой по конце сезона первые 4 команды попадут в Кубок."
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# Команда /Page2
async def page2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "✨ **Page 2**\n\n"
        "Также по конце всего будет проведена церемония с позингами, "
        "в которую ты сможешь попасть!"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# --- ЗАПУСК БОТА ---
def main():
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("Page1", page1))
    application.add_handler(CommandHandler("Page2", page2))

    print("Бот запущен! Проверь команды /start, /Page1 и /Page2")
    application.run_polling()

if __name__ == '__main__':
    main()
