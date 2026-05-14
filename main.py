import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Твой токен
TOKEN = '8067572893:AAH0Lx_Dq2lENkuTDoHQO1v46NTe8WLWEpo'

# Настройка логов, чтобы видеть ошибки в консоли
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# Функция, которая будет отвечать на /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('привет')

def main():
    # Создаем приложение бота
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Запускаем бота
    print("Бот запущен. Напиши ему /start в Телеграм!")
    application.run_polling()

if __name__ == '__main__':
    main()
