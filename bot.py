import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from config import BOT_TOKEN
from services import add_film_from_kinopoisk, get_random_film, get_all_films, search_films_kinopoisk, get_film_details_kinopoisk, mark_film_watched, delete_film, get_watched_films
from database import engine, Base
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Главное меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅Добавить фильм")],
        [KeyboardButton(text="👀Случайный фильм"), KeyboardButton(text="📋Список фильмов")],
        [KeyboardButton(text="🧹Очистить чат"), KeyboardButton(text="⭐Просмотренные фильмы")],
    ],
    resize_keyboard=True
)

class AddFilmStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_choice = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Добро пожаловать в Фильмотеку 🎬\nВыберите действие:", reply_markup=main_kb)

@dp.message(F.text == "✅Добавить фильм")
async def ask_film_title(message: types.Message, state: FSMContext):
    await message.answer("Введите название фильма для поиска:")
    await state.set_state(AddFilmStates.waiting_for_title)

@dp.message(AddFilmStates.waiting_for_title)
async def show_film_choices(message: types.Message, state: FSMContext):
    films = await search_films_kinopoisk(message.text.strip())
    if not films:
        await message.answer("Фильмы не найдены. Попробуйте другое название.")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{film['title']} ({film['year'] or '—'})", callback_data=f"choose_{film['kinopoiskId']}")]
            for film in films
        ] + [[InlineKeyboardButton(text="Отмена", callback_data="cancel_add")]]
    )
    await state.update_data(films=films)
    await message.answer("Выберите фильм из найденных:", reply_markup=kb)
    await state.set_state(AddFilmStates.waiting_for_choice)

@dp.callback_query(AddFilmStates.waiting_for_choice, F.data.startswith("choose_"))
async def show_film_details_for_add(callback: types.CallbackQuery, state: FSMContext):
    film_id = str(callback.data.split("_", 1)[1])
    film = await get_film_details_kinopoisk(film_id)
    if not film:
        await callback.answer("Не удалось получить подробности фильма. Попробуйте позже.", show_alert=True)
        return
    text = f"🎥 <b>{film['title']}</b>\nГод: {film['year'] or '—'}\nЖанр: {film['genre'] or '—'}"
    if film['description']:
        text += f"\nОписание: {film['description']}"
    if film['director']:
        text += f"\nРежиссер: {film['director']}"
    if film['actors']:
        text += f"\nАктеры: {film['actors']}"
    if film['country']:
        text += f"\nСтрана: {film['country']}"
    if film['rating']:
        text += f"\nРейтинг Кинопоиск: {film['rating']}"
    if film['trailer_url']:
        text += f"\n<a href='{film['trailer_url']}'>Трейлер</a>"
    if film['poster_url']:
        text += f"\n<a href='{film['poster_url']}'>Постер</a>"
    if film.get('watch_url'):
        text += f"\n<a href='{film['watch_url']}'>Смотреть онлайн</a>"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить этот фильм", callback_data=f"add_{film_id}")],
            [InlineKeyboardButton(text="Назад к списку", callback_data="back_to_list")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_add")]
        ]
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    await state.update_data(selected_film=film)

@dp.callback_query(AddFilmStates.waiting_for_choice, F.data.startswith("add_"))
async def confirm_add_film(callback: types.CallbackQuery, state: FSMContext):
    film_id = int(callback.data.split("_", 1)[1])
    data = await state.get_data()
    film = data.get("selected_film")
    if not film or film["kinopoiskId"] != film_id:
        await callback.answer("Ошибка добавления.", show_alert=True)
        return
    await add_film_from_kinopoisk(film)
    await callback.message.edit_text("Фильм успешно добавлен в коллекцию!", reply_markup=None)
    await state.clear()

@dp.callback_query(AddFilmStates.waiting_for_choice, F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    films = data.get("films", [])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{film['title']} ({film['year'] or '—'})", callback_data=f"choose_{film['kinopoiskId']}")]
            for film in films
        ] + [[InlineKeyboardButton(text="Отмена", callback_data="cancel_add")]]
    )
    await callback.message.edit_text("Выберите фильм из найденных:", reply_markup=kb)

@dp.callback_query(AddFilmStates.waiting_for_choice, F.data == "cancel_add")
async def cancel_add_film(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Добавление фильма отменено.", reply_markup=None)
    await state.clear()

@dp.message(F.text == "👀Случайный фильм")
async def cmd_random(message: types.Message):
    film = await get_random_film()
    if film:
        text = f"🎥 <b>{film.title}</b>\nГод: {film.year or '—'}\nЖанр: {film.genre or '—'}"
        if film.description:
            text += f"\nОписание: {film.description}"
        if film.trailer_url:
            text += f"\n<a href='{film.trailer_url}'>Трейлер</a>"
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await message.answer("Фильмотека пуста.")

@dp.message(F.text == "📋Список фильмов")
async def cmd_list(message: types.Message):
    films = await get_all_films()
    if not films:
        return await message.answer("Список пуст.")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Подробнее: {film.title}", callback_data=f"details_{film.id}")]
            for film in films
        ]
    )
    await message.answer("Выберите фильм для подробностей:", reply_markup=kb)

@dp.callback_query(F.data.startswith("details_"))
async def show_film_details(callback: types.CallbackQuery):
    film_id = int(callback.data.split("_", 1)[1])
    films = await get_all_films()
    film = next((f for f in films if f.id == film_id), None)
    if film:
        text = f"🎥 <b>{film.title}</b>\nГод: {film.year or '—'}\nЖанр: {film.genre or '—'}"
        if film.description:
            text += f"\nОписание: {film.description}"
        if film.director:
            text += f"\nРежиссер: {film.director}"
        if film.actors:
            text += f"\nАктеры: {film.actors}"
        if film.country:
            text += f"\nСтрана: {film.country}"
        if film.rating:
            text += f"\nРейтинг Кинопоиск: {film.rating}"
        if film.trailer_url:
            text += f"\n<a href='{film.trailer_url}'>Трейлер</a>"
        if film.poster_url:
            text += f"\n<a href='{film.poster_url}'>Постер</a>"
        if film.watch_url:
            text += f"\n<a href='{film.watch_url}'>Смотреть онлайн</a>"
        watched_text = "✅ Просмотрено" if film.watched else "❌ Не просмотрено"
        text += f"\n{watched_text}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{film.id}"),
                 InlineKeyboardButton(text="Отметить как просмотренный", callback_data=f"watched_{film.id}")]
            ]
        )
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_"))
async def delete_film_callback(callback: types.CallbackQuery):
    film_id = int(callback.data.split("_", 1)[1])
    await delete_film(film_id)
    await callback.message.edit_text("Фильм удалён из коллекции.")
    await callback.answer()

@dp.callback_query(F.data.startswith("watched_"))
async def watched_film_callback(callback: types.CallbackQuery):
    film_id = int(callback.data.split("_", 1)[1])
    await mark_film_watched(film_id)
    await callback.message.edit_text("Фильм отмечен как просмотренный!")
    await callback.answer()

@dp.message(F.text == "⭐Просмотренные фильмы")
async def watched_list(message: types.Message):
    films = await get_watched_films()
    if not films:
        return await message.answer("Список просмотренных фильмов пуст.")
    text = "\n".join([f"• {film.title} ({film.year or '—'})" for film in films])
    await message.answer("⭐ Просмотренные фильмы:\n" + text)

@dp.message(F.text == "🧹Очистить чат")
async def clear_chat(message: types.Message):
    await message.answer("Чат очищен! (Удалите сообщения вручную, если нужно)")

@dp.message()
async def handle_text(message: types.Message):
    # Если пользователь вводит название фильма после "Добавить фильм"
    if message.reply_to_message and message.reply_to_message.text.startswith("Введите название фильма"):
        title = message.text.strip()
        await add_film_from_kinopoisk(title)
        film = await search_films_kinopoisk(title)
        if film:
            text = f"🎥 <b>{film['title']}</b>\nГод: {film['year'] or '—'}\nЖанр: {film['genre'] or '—'}"
            if film['description']:
                text += f"\nОписание: {film['description']}"
            if film['trailer_url']:
                text += f"\n<a href='{film['trailer_url']}'>Трейлер</a>"
            await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await message.answer("Фильм добавлен!")
    else:
        await message.answer("Пожалуйста, используйте кнопки меню для управления ботом.", reply_markup=main_kb)

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 