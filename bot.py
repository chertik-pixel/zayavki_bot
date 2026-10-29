import asyncio
import csv                      
import logging
import os                       
from datetime import datetime   
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)

load_dotenv()  # читает файл .env

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

dp = Dispatcher()

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Услуги"), KeyboardButton(text="💰 Цены")],
        [KeyboardButton(text="📝 Оставить заявку")],
        [KeyboardButton(text="📞 Контакты")],
        [KeyboardButton(text="🕐 Часы работы")],
    ],
    resize_keyboard=True,
)

# НОВОЕ: услуги записаны в ОДНОМ месте
SERVICES = ["Стрижка", "Окрашивание", "Укладка"]
CANCEL = "❌ Отмена"

# НОВОЕ: клавиатура строится из списка — по кнопке в ряд + «Отмена»
service_rows = []
for s in SERVICES:
    service_rows.append([KeyboardButton(text=s)])
service_rows.append([KeyboardButton(text=CANCEL)])
services_kb = ReplyKeyboardMarkup(keyboard=service_rows, resize_keyboard=True)

# НОВОЕ: клавиатура только с «Отменой» — для шагов «имя» и «телефон»
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=CANCEL)]],
    resize_keyboard=True,
)

FILE = "zayavki.csv"


def save_request(data):
    is_new = not os.path.exists(FILE)
    with open(FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        if is_new:
            writer.writerow(["Дата", "Имя", "Телефон", "Услуга", "Ник"])
        writer.writerow([
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            data["name"],
            data["phone"],
            data["service"],
            data["username"],
        ])
        

class Form(StatesGroup):
    name = State()
    phone = State()
    service = State()


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! Выбери, что тебя интересует:",
        reply_markup=menu,
    )


@dp.message(Command("id"))
async def my_id(message: Message):
    await message.answer(f"Твой ID: {message.from_user.id}")

# НОВОЕ: админ получает файл со всеми заявками
@dp.message(Command("zayavki"))
async def send_file(message: Message):
    if message.from_user.id != ADMIN_ID:
        return  # чужим ничего не отвечаем
    if not os.path.exists(FILE):
        await message.answer("Заявок пока нет.")
        return
    await message.answer_document(FSInputFile(FILE), caption="Все заявки")
    
    
@dp.message(F.text == "📋 Услуги")
async def services(message: Message):
    text = "Мы делаем:"
    for s in SERVICES:
        text += "\n— " + s
    await message.answer(text)


@dp.message(F.text == "💰 Цены")
async def prices(message: Message):
    await message.answer("Стрижка — 1500 ₽\nОкрашивание — от 3000 ₽\nУкладка — 1000 ₽")


@dp.message(F.text == "📞 Контакты")
async def contacts(message: Message):
    await message.answer("Адрес: ул. Примерная, 1\nТелефон: +7 900 000-00-00")


@dp.message(F.text == "🕐 Часы работы")
async def hours(message: Message):
    await message.answer("Пн–Сб 10:00–20:00")


# НОВОЕ: отмена. Стоит ВЫШЕ шагов анкеты!
@dp.message(F.text == CANCEL)
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена.", reply_markup=menu)


@dp.message(F.text == "📝 Оставить заявку")
async def form_start(message: Message, state: FSMContext):
    await state.set_state(Form.name)
    await message.answer("Как вас зовут?", reply_markup=cancel_kb)  # НОВОЕ


@dp.message(Form.name, F.text)
async def form_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.phone)
    await message.answer("Ваш номер телефона?", reply_markup=cancel_kb)  # НОВОЕ


@dp.message(Form.phone, F.text)
async def form_phone(message: Message, state: FSMContext):
    digits = 0
    for ch in message.text:
        if ch.isdigit():
            digits += 1
    if digits < 10:
        await message.answer("Похоже, в номере ошибка. Напишите полностью, например: +7 900 123-45-67")
        return

    await state.update_data(phone=message.text)
    await state.set_state(Form.service)
    await message.answer("Выберите услугу:", reply_markup=services_kb)  # НОВОЕ


@dp.message(Form.service, F.text)
async def form_service(message: Message, state: FSMContext):
    if message.text not in SERVICES:
        await message.answer("Выберите услугу кнопкой ниже 👇", reply_markup=services_kb)
        return

    username = message.from_user.username
    if username is None:
        username = "нет ника"
    else:
        username = "@" + username

    await state.update_data(service=message.text, username=username)
    data = await state.get_data()
    await state.clear()

    save_request(data)  # НОВОЕ: сначала в файл

    # НОВОЕ: если отправка админу упадёт, бот не сломается
    try:
        await message.bot.send_message(
            ADMIN_ID,
            f"📝 Новая заявка!\nИмя: {data['name']}\nТелефон: {data['phone']}\nУслуга: {data['service']}\nTelegram: {data['username']}",
        )
    except Exception as e:
        logging.error(f"Не удалось отправить заявку админу: {e}")

    await message.answer("Спасибо! Мы скоро с вами свяжемся.", reply_markup=menu)   


@dp.message()
async def unknown(message: Message):
    await message.answer("Не понял 🤔 Нажми кнопку в меню.", reply_markup=menu)


async def main():
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())