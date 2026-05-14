import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Твои данные
API_TOKEN = '8067572893:AAH0Lx_Dq2lENkuTDoHQO1v46NTe8WLWEpo'
ADMIN_ID = 7908057052

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния для создания матча
class MatchSetup(StatesGroup):
    choosing_team1 = State()
    choosing_team2 = State()
    setting_time = State()

# База данных в памяти
db = {
    "players": {}, 
    "clubs": []  # Сюда добавляются команды через /add_club
}

# --- Клавиатуры ---

def get_player_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="/Ready")
    kb.button(text="/UnReady")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def get_clubs_keyboard():
    builder = InlineKeyboardBuilder()
    for club in db["clubs"]:
        builder.button(text=club, callback_data=f"select_club:{club}")
    builder.adjust(1)
    return builder.as_markup()

# --- Хендлеры игроков ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id in db["players"]:
        club = db["players"][user_id]["club"]
        await message.answer(f"✅ Вы в клубе: **{club}**", reply_markup=get_player_kb(), parse_mode="Markdown")
    else:
        await message.answer("❌ Вы не привязаны. Попросите @Verybigsun привязать вас.")

@dp.message(Command("Ready"))
async def cmd_ready(message: types.Message):
    if message.from_user.id not in db["players"]: return
    await message.answer("✅ Ты подтвердил участие!")
    await bot.send_message(ADMIN_ID, f"🟢 **ГОТОВ**: {message.from_user.full_name} ({db['players'][message.from_user.id]['club']})")

@dp.message(Command("UnReady"))
async def cmd_unready(message: types.Message):
    if message.from_user.id not in db["players"]: return
    await message.answer("❌ Записал, что тебя не будет.")
    await bot.send_message(ADMIN_ID, f"🔴 **ОТКАЗ**: {message.from_user.full_name} ({db['players'][message.from_user.id]['club']})")

# --- Админ-панель: Создание матча ---

@dp.message(Command("Admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer(
        "🛠 **Админка**\n\n"
        "1. `/add_club Название` — Добавить команду в список\n"
        "2. `/bind ID Название` — Привязать игрока к клубу\n"
        "3. `/match` — Создать новый сбор на игру", 
        parse_mode="Markdown"
    )

@dp.message(Command("add_club"))
async def add_club(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    club_name = message.text.replace("/add_club ", "").strip()
    if club_name and club_name not in db["clubs"]:
        db["clubs"].append(club_name)
        await message.answer(f"✅ Команда **{club_name}** добавлена.")
    else:
        await message.answer("Введите название или такая команда уже есть.")

@dp.message(Command("match"))
async def start_match_creation(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not db["clubs"]:
        return await message.answer("Сначала добавьте команды через `/add_club`")
    
    await state.set_state(MatchSetup.choosing_team1)
    await message.answer("Выбери **Первую команду**:", reply_markup=get_clubs_keyboard())

@dp.callback_query(MatchSetup.choosing_team1)
async def team1_chosen(callback: types.CallbackQuery, state: FSMContext):
    club = callback.data.split(":")[1]
    await state.update_data(team1=club)
    await state.set_state(MatchSetup.choosing_team2)
    await callback.message.edit_text(f"Выбрано: {club}\nТеперь выбери **Вторую команду**:", reply_markup=get_clubs_keyboard())

@dp.callback_query(MatchSetup.choosing_team2)
async def team2_chosen(callback: types.CallbackQuery, state: FSMContext):
    club = callback.data.split(":")[1]
    data = await state.get_data()
    if club == data['team1']:
        return await callback.answer("Выбери другую команду, нельзя играть с самим собой!")
    
    await state.update_data(team2=club)
    await state.set_state(MatchSetup.setting_time)
    await callback.message.edit_text(f"Матч: {data['team1']} vs {club}\n\nНапиши **дату и время** матча (например: 20 мая в 18:00):")

@dp.message(MatchSetup.setting_time)
async def finish_match_creation(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    time_str = message.text
    data = await state.get_data()
    await state.clear()

    match_text = (
        f"📢 **НОВЫЙ МАТЧ!**\n\n"
        f"🏟 **{data['team1']}** vs **{data['team2']}**\n"
        f"⏰ Время: **{time_str}**\n\n"
        f"Просьба всем игрокам дать отпись кнопками /Ready или /UnReady!"
    )

    # Рассылка всем привязанным игрокам
    sent_count = 0
    for user_id in db["players"]:
        try:
            await bot.send_message(user_id, match_text, parse_mode="Markdown")
            sent_count += 1
        except:
            pass
    
    await message.answer(f"✅ Сбор разослан {sent_count} игрокам!")

@dp.message(Command("bind"))
async def bind_player(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(maxsplit=2)
        target_id, club_name = int(parts[1]), parts[2]
        db["players"][target_id] = {"club": club_name}
        await message.answer(f"✅ Игрок {target_id} привязан к {club_name}")
        await bot.send_message(target_id, f"🎉 Вы привязаны к клубу **{club_name}**!")
    except:
        await message.answer("Ошибка. Формат: `/bind ID Название`")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
