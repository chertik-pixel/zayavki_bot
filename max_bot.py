import asyncio
import csv
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from maxapi import Bot, Dispatcher, F
from maxapi.context import MemoryContext, State, StatesGroup
from maxapi.filters.command import Command, CommandStart
from maxapi.types import BotStarted, InputMedia, MessageCreated
from maxapi.types.attachments.buttons import MessageButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("MAX_TOKEN")
ADMIN_ID = int(os.getenv("MAX_ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

SERVICES = ["Стрижка", "Окрашивание", "Укладка"]
CANCEL = "❌ Отмена"
GREETING = "Здравствуйте! Выберите, что вас интересует:"
FILE = "zayavki_max.csv"    


# ---------- Клавиатуры ----------
def menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(MessageButton(text="📋 Услуги"), MessageButton(text="💰 Цены"))
    kb.row(MessageButton(text="📝 Оставить заявку"))
    kb.row(MessageButton(text="📞 Контакты"), MessageButton(text="🕐 Часы работы"))
    return kb.as_markup()


def services_kb():
    kb = InlineKeyboardBuilder()
    for s in SERVICES:
        kb.row(MessageButton(text=s))
    kb.row(MessageButton(text=CANCEL))
    return kb.as_markup()


def cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.row(MessageButton(text=CANCEL))
    return kb.as_markup()


# ---------- Файл с заявками ----------
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


# ---------- Старт ----------
@dp.bot_started()
async def on_start_button(event: BotStarted):
    await bot.send_message(chat_id=event.chat_id, text=GREETING, attachments=[menu_kb()])


@dp.message_created(CommandStart())
async def start(event: MessageCreated, context: MemoryContext):
    await context.clear()
    await event.message.answer(GREETING, attachments=[menu_kb()])


@dp.message_created(Command("id"))
async def my_id(event: MessageCreated):
    await event.message.answer(f"Твой ID: {event.message.sender.user_id}")


@dp.message_created(Command("zayavki"))
async def send_file(event: MessageCreated):
    if event.message.sender.user_id != ADMIN_ID:
        return
    if not os.path.exists(FILE):
        await event.message.answer("Заявок пока нет.")
        return
    await event.message.answer("Все заявки", attachments=[InputMedia(path=FILE)])


# ---------- Меню ----------
@dp.message_created(F.message.body.text == "📋 Услуги")
async def services(event: MessageCreated):
    text = "Мы делаем:"
    for s in SERVICES:
        text += "\n— " + s
    await event.message.answer(text, attachments=[menu_kb()])


@dp.message_created(F.message.body.text == "💰 Цены")
async def prices(event: MessageCreated):
    await event.message.answer("Стрижка — 1500 ₽\nОкрашивание — от 3000 ₽\nУкладка — 1000 ₽", attachments=[menu_kb()])


@dp.message_created(F.message.body.text == "📞 Контакты")
async def contacts(event: MessageCreated):
    await event.message.answer("Адрес: ул. Примерная, 1\nТелефон: +7 900 000-00-00", attachments=[menu_kb()])


@dp.message_created(F.message.body.text == "🕐 Часы работы")
async def hours(event: MessageCreated):
    await event.message.answer("Пн–Сб 10:00–20:00", attachments=[menu_kb()])


# ---------- Анкета ----------
# Отмена — ВЫШЕ шагов анкеты
@dp.message_created(F.message.body.text == CANCEL)
async def cancel(event: MessageCreated, context: MemoryContext):
    await context.clear()
    await event.message.answer("Заявка отменена.", attachments=[menu_kb()])


@dp.message_created(F.message.body.text == "📝 Оставить заявку")
async def form_start(event: MessageCreated, context: MemoryContext):
    await context.set_state(Form.name)
    await event.message.answer("Как вас зовут?", attachments=[cancel_kb()])


@dp.message_created(F.message.body.text, Form.name)
async def form_name(event: MessageCreated, context: MemoryContext):
    await context.update_data(name=event.message.body.text)
    await context.set_state(Form.phone)
    await event.message.answer("Ваш номер телефона?", attachments=[cancel_kb()])


@dp.message_created(F.message.body.text, Form.phone)
async def form_phone(event: MessageCreated, context: MemoryContext):
    text = event.message.body.text
    digits = 0
    for ch in text:
        if ch.isdigit():
            digits += 1
    if digits < 10:
        await event.message.answer(
            "Похоже, в номере ошибка. Напишите полностью, например: +7 900 123-45-67",
            attachments=[cancel_kb()],
        )
        return

    await context.update_data(phone=text)
    await context.set_state(Form.service)
    await event.message.answer("Выберите услугу:", attachments=[services_kb()])


@dp.message_created(F.message.body.text, Form.service)
async def form_service(event: MessageCreated, context: MemoryContext):
    text = event.message.body.text
    if text not in SERVICES:
        await event.message.answer("Выберите услугу кнопкой ниже 👇", attachments=[services_kb()])
        return

    username = event.message.sender.username
    if username is None:
        username = "нет ника"
    else:
        username = "@" + username

    await context.update_data(service=text, username=username)
    data = await context.get_data()
    await context.clear()

    save_request(data)

    try:
        await bot.send_message(
            user_id=ADMIN_ID,
            text=f"📝 Новая заявка!\nИмя: {data['name']}\nТелефон: {data['phone']}\nУслуга: {data['service']}\nMAX: {data['username']}",
        )
    except Exception as e:
        logging.error(f"Не удалось отправить заявку админу: {e}")

    await event.message.answer("Спасибо! Мы скоро с вами свяжемся.", attachments=[menu_kb()])


# Всё остальное. ВСЕГДА последний
@dp.message_created(F.message.body.text)
async def unknown(event: MessageCreated):
    await event.message.answer("Не понял 🤔 Нажмите кнопку в меню.", attachments=[menu_kb()])


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())