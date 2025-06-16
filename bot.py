import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from config import BOT_TOKEN
from services import add_film_from_kinopoisk, get_random_film, get_all_films, search_films_kinopoisk, get_film_details_kinopoisk, mark_film_watched, delete_film, get_watched_films
from database import engine, Base
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Главное меню с учётом профиля
def get_main_kb(profile):
    if profile == "Евгеша":
        other = "Вандронович"
    else:
        other = "Евгеша"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅Добавить фильм")],
            [KeyboardButton(text="⭐ Список просмотренных"), KeyboardButton(text="📋Список фильмов")],
            [KeyboardButton(text=f"📂 Фильмы {other}")],
            [KeyboardButton(text="🔄 Перезапустить бота")],
        ],
        resize_keyboard=True
    )

class AddFilmStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_choice = State()

class UserStates(StatesGroup):
    choosing_user = State()
    user_selected = State()

class RateCommentStates(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()

user_list = ["Евгеша", "Вандронович"]

def ensure_profile(func):
    async def wrapper(*args, **kwargs):
        state = kwargs.get("state")
        message = kwargs.get("message")
        callback = kwargs.get("callback")
        event = kwargs.get("event")

        # aiogram обычно передаёт message/callback как первый аргумент, state — второй
        if state is None and len(args) > 1:
            state = args[1]
        if message is None and callback is None:
            if len(args) > 0:
                if hasattr(args[0], "text"):  # message
                    message = args[0]
                elif hasattr(args[0], "data"):  # callback_query
                    callback = args[0]
                elif hasattr(args[0], "message"):  # event
                    event = args[0]
        # Проверяем профиль
        if state is not None:
            data = await state.get_data()
            if not data.get("profile"):
                if message:
                    await message.answer("Сначала выберите пользователя через /start.")
                elif callback:
                    await callback.message.answer("Сначала выберите пользователя через /start.")
                elif event:
                    await event.message.answer("Сначала выберите пользователя через /start.")
                await state.set_state(UserStates.choosing_user)
                return
        return await func(*args, **kwargs)
    return wrapper

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=name)] for name in user_list],
        resize_keyboard=True
    )
    await message.answer("Выберите пользователя:", reply_markup=kb)
    await state.set_state(UserStates.choosing_user)

@dp.message(UserStates.choosing_user)
async def choose_user(message: types.Message, state: FSMContext):
    if message.text not in user_list:
        await message.answer("Пожалуйста, выберите пользователя из списка.")
        return
    await state.update_data(profile=message.text)
    await state.set_state(UserStates.user_selected)
    await message.answer(f"Профиль {message.text} выбран!", reply_markup=get_main_kb(message.text))

@dp.message(StateFilter(UserStates.user_selected), F.text == "✅Добавить фильм")
@ensure_profile
async def ask_film_title(message: types.Message, state: FSMContext, **kwargs):
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
    profile = data.get("profile")
    if not film or film["kinopoiskId"] != film_id:
        await callback.answer("Ошибка добавления.", show_alert=True)
        return
    await add_film_from_kinopoisk(film, profile)
    await callback.message.edit_text("Фильм успешно добавлен в коллекцию!", reply_markup=None)
    await state.clear()
    await state.set_state(UserStates.user_selected)
    await state.update_data(profile=profile)

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
    await state.set_state(UserStates.user_selected)
    await state.update_data(selected_film=None)

@dp.message(StateFilter(UserStates.user_selected), F.text == "⭐ Список просмотренных")
@ensure_profile
async def watched_list(message: types.Message, state: FSMContext, **kwargs):
    data = await state.get_data()
    profile = data.get("profile")
    films = await get_watched_films(profile)
    if not films:
        return await message.answer("Список просмотренных фильмов пуст.")
    text = "\n".join([f"• {film.title} ({film.year or '—'})" for film in films])
    await message.answer("⭐ Просмотренные фильмы:\n" + text)

@dp.message(StateFilter(UserStates.user_selected), F.text == "📋Список фильмов")
@ensure_profile
async def cmd_list(message: types.Message, state: FSMContext, **kwargs):
    data = await state.get_data()
    profile = data.get("profile")
    films = await get_all_films(profile)
    if not films:
        return await message.answer("Список пуст.")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Подробнее: {film.title}", callback_data=f"details_{film.id}")]
            for film in films
        ]
    )
    await message.answer("Выберите фильм для подробностей:", reply_markup=kb)

@dp.callback_query(StateFilter(UserStates.user_selected), F.data.startswith("details_"))
@ensure_profile
async def show_film_details(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    data = await state.get_data()
    profile = data.get("profile")
    films = await get_all_films(profile)
    film_id = int(callback.data.split("_", 1)[1])
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
        if film.rating_user:
            text += f"\nВаша оценка: {film.rating_user}/10"
        if film.comment_user:
            text += f"\nВаш комментарий: {film.comment_user}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Поставить оценку", callback_data=f"rate_{film.id}"),
                 InlineKeyboardButton(text="Оставить комментарий", callback_data=f"comment_{film.id}")],
                [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{film.id}"),
                 InlineKeyboardButton(text="Отметить как просмотренный", callback_data=f"watched_{film.id}")]
            ]
        )
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(StateFilter(UserStates.user_selected), F.data.startswith("delete_"))
async def delete_film_callback(callback: types.CallbackQuery):
    film_id = int(callback.data.split("_", 1)[1])
    await delete_film(film_id)
    await callback.message.edit_text("Фильм удалён из коллекции.")
    await callback.answer()

@dp.callback_query(StateFilter(UserStates.user_selected), F.data.startswith("watched_"))
async def watched_film_callback(callback: types.CallbackQuery):
    film_id = int(callback.data.split("_", 1)[1])
    await mark_film_watched(film_id)
    await callback.message.edit_text("Фильм отмечен как просмотренный!")
    await callback.answer()

@dp.callback_query(StateFilter(UserStates.user_selected), F.data.startswith("rate_"))
@ensure_profile
async def rate_film(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    film_id = int(callback.data.split("_", 1)[1])
    await state.update_data(rate_film_id=film_id)
    await callback.message.answer("Введите вашу оценку фильму (1-10):")
    await state.set_state(RateCommentStates.waiting_for_rating)
    await callback.answer()

@dp.message(RateCommentStates.waiting_for_rating)
async def save_rating(message: types.Message, state: FSMContext):
    try:
        rating = int(message.text.strip())
        if not (1 <= rating <= 10):
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите целое число от 1 до 10.")
        return
    data = await state.get_data()
    film_id = data.get("rate_film_id")
    profile = data.get("profile")
    # Обновляем оценку в базе
    from services import SessionLocal, Film
    async with SessionLocal() as session:
        film = await session.get(Film, film_id)
        if film and film.profile == profile:
            film.rating_user = rating
            await session.commit()
    await message.answer(f"Ваша оценка {rating}/10 сохранена!")
    await state.set_state(UserStates.user_selected)

@dp.callback_query(StateFilter(UserStates.user_selected), F.data.startswith("comment_"))
@ensure_profile
async def comment_film(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    film_id = int(callback.data.split("_", 1)[1])
    await state.update_data(comment_film_id=film_id)
    await callback.message.answer("Введите ваш комментарий к фильму (до 500 символов):")
    await state.set_state(RateCommentStates.waiting_for_comment)
    await callback.answer()

@dp.message(RateCommentStates.waiting_for_comment)
async def save_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    if len(comment) > 500:
        await message.answer("Комментарий слишком длинный. Пожалуйста, до 500 символов.")
        return
    data = await state.get_data()
    film_id = data.get("comment_film_id")
    profile = data.get("profile")
    from services import SessionLocal, Film
    async with SessionLocal() as session:
        film = await session.get(Film, film_id)
        if film and film.profile == profile:
            film.comment_user = comment
            await session.commit()
    await message.answer("Комментарий сохранён!")
    await state.set_state(UserStates.user_selected)

@dp.message(StateFilter(UserStates.user_selected), F.text == "🔄 Перезапустить бота")
@ensure_profile
async def restart_bot(message: types.Message, state: FSMContext, **kwargs):
    await message.answer("Бот будет перезапущен. Пожалуйста, перезапустите процесс вручную (или используйте supervisor/systemd, если настроено).")
    # Для ручного завершения процесса (если нужно):
    # import os; os._exit(0)

@dp.message(StateFilter(UserStates.user_selected), F.text.regexp(r"^📂 Фильмы "))
@ensure_profile
async def other_user_films(message: types.Message, state: FSMContext, **kwargs):
    data = await state.get_data()
    profile = data.get("profile")
    other = "Вандронович" if profile == "Евгеша" else "Евгеша"
    films = await get_all_films(other)
    if not films:
        return await message.answer(f"У пользователя {other} нет фильмов.")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Подробнее: {film.title}", callback_data=f"otherdetails_{film.id}")]
            for film in films
        ]
    )
    await message.answer(f"Фильмы пользователя {other}:", reply_markup=kb)

@dp.callback_query(StateFilter(UserStates.user_selected), F.data.startswith("otherdetails_"))
@ensure_profile
async def show_other_film_details(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    data = await state.get_data()
    profile = data.get("profile")
    other = "Вандронович" if profile == "Евгеша" else "Евгеша"
    films = await get_all_films(other)
    film_id = int(callback.data.split("_", 1)[1])
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
        if film.rating_user:
            text += f"\nОценка: {film.rating_user}/10"
        if film.comment_user:
            text += f"\nКомментарий: {film.comment_user}"
        await callback.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()

@dp.message()
async def handle_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get("profile"):
        await state.set_state(UserStates.user_selected)
        await message.answer("Пожалуйста, используйте кнопки меню для управления ботом.", reply_markup=get_main_kb(data.get("profile")))
    else:
        await message.answer("Сначала выберите пользователя через /start.")

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 