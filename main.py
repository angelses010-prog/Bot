import asyncio
import logging
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- НАСТРОЙКИ ---
API_TOKEN = '8067572893:AAH0Lx_Dq2lENkuTDoHQO1v46NTe8WLWEpo'
ADMIN_ID = 7908057052
DB_FILE = 'database.json'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- ЛОГИКА БАЗЫ ДАННЫХ (JSON) ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"players": {}, "clubs": []}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_db()

# --- СОСТОЯНИЯ ДЛЯ МАШИНЫ СОСТОЯНИЙ (FSM) ---
class MatchSetup(StatesGroup):
    choosing_team1 = State()
    choosing_team2 = State()
    setting_time = State()

# --- КЛАВИАТУРЫ ---
def get_player_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="/Ready")
    kb.button(text="/UnReady")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

def get_clubs_keyboard():
    builder = InlineKeyboardBuilder()
    for club in db["clubs"]:
        builder.button(text=club, callback_data=f"sel:{club}")
    builder.adjust(1)
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ИГРОКОВ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id in db["players"]:
        club = db["players"][user_id]["club"]
        await message.answer(f"✅ Вы привязаны к клубу: **{club}**", reply_markup=get_player_kb(), parse_mode="Markdown")
    else:
        await message.answer("❌ Вы не привязаны к клубу. Попросите @Verybigsun привязать вас.")

@dp.message(Command("Ready"))
async def cmd_ready(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in db["players"]: return
    await message.answer("✅ Ты подтвердил участие!")
    await bot.send_message(ADMIN_ID, f"🟢 **ГОТОВ**: {message.from_user.full_name} (@{message.from_user.username or 'no_nick'}) — {db['players'][user_id]['club']}")

@dp.message(Command("UnReady"))
async def cmd_unready(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in db["players"]: return
    await message.answer("❌ Записал, что тебя не будет.")
    await bot.send_message(ADMIN_ID, f"🔴 **ОТКАЗ**: {message.from_user.full_name} (@{message.from_user.username or 'no_nick'}) — {db['players'][user_id]['club']}")

# --- АДМИН-КОМАНДЫ ---
@dp.message(Command("Admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer(
        "🛠 **Панель админа**\n\n"
        "1️⃣ `/add_club Название` — Добавить команду\n"
        "2️⃣ `/bind ID Название` — Привязать игрока\n"
        "3️⃣ `/match` — Создать сбор на игру",
        parse_mode="Markdown"
    )

@dp.message(Command("add_club"))
async def add_club(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    name = message.text.replace("/add_club ", "").strip()
    if name and name not in db["clubs"]:
        db["clubs"].append(name)
        save_db(db)
        await message.answer(f"✅ Команда **{name}** добавлена.")

@dp.message(Command("bind"))
async def bind_player(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split(maxsplit=2)
        target_id, club_name = parts[1], parts[2]
        db["players"][target_id] = {"club": club_name, "name": "Unknown"}
        save_db(db)
        await message.answer(f"✅ Игрок {target_id} привязан к {club_name}")
        try:
            await bot.send_message(int(target_id), f"🎉 Тебя привязали к клубу **{club_name}**!")
        except: pass
    except:
        await message.answer("Ошибка! Формат: `/bind 12345678 НазваниеКоманды`")

# --- ПРОЦЕСС СОЗДАНИЯ МАТЧА ---
@dp.message(Command("match"))
async def start_match(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not db["clubs"]:
        return await message.answer("Сначала добавь команды: `/add_club Название`")
    await state.set_state(MatchSetup.choosing_team1)
    await message.answer("Выбери **Первую команду**:", reply_markup=get_clubs_keyboard())

@dp.callback_query(F.data.startswith("sel:"), MatchSetup.choosing_team1)
async def t1_selected(callback: types.CallbackQuery, state: FSMContext):
    club = callback.data.split(":")[1]
    await state.update_data(t1=club)
    await state.set_state(MatchSetup.choosing_team2)
    await callback.message.edit_text(f"Команда 1: {club}\nВыбери **Вторую команду**:", reply_markup=get_clubs_keyboard())

@dp.callback_query(F.data.startswith("sel:"), MatchSetup.choosing_team2)
async def t2_selected(callback: types.CallbackQuery, state: FSMContext):
    club = callback.data.split(":")[1]
    data = await state.get_data()
    if club == data['t1']:
        return await callback.answer("Нельзя выбрать ту же команду!")
    await state.update_data(t2=club)
    await state.set_state(MatchSetup.setting_time)
    await callback.message.edit_text(f"Матч: {data['t1']} vs {club}\n\nВведи дату и время (текстом):")

@dp.message(MatchSetup.setting_time)
async def set_time(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    time_val = message.text
    data = await state.get_data()
    await state.clear()

    msg = (f"📢 **НОВЫЙ МАТЧ!**\n\n🏟 **{data['t1']}** vs **{data['t2']}**\n"
           f"⏰ Время: **{time_val}**\n\n"
           f"Жми /Ready если будешь, или /UnReady если нет!")

    count = 0
    for uid in db["players"]:
        try:
            await bot.send_message(int(uid), msg, parse_mode="Markdown")
            count += 1
        except: pass
    await message.answer(f"✅ Сбор отправлен {count} игрокам.")

async def main():
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
