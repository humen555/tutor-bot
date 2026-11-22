import asyncio
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# Гибридная загрузка настроек: сначала ищем в переменных окружения (для хостинга),
# если их нет — берём из локального файла config.py (для ноутбука).
BOT_TOKEN = os.getenv("BOT_TOKEN")
TUTOR_ID_RAW = os.getenv("TUTOR_ID")

if not BOT_TOKEN or not TUTOR_ID_RAW:
    try:
        import config

        BOT_TOKEN = BOT_TOKEN or config.BOT_TOKEN
        TUTOR_ID_RAW = TUTOR_ID_RAW or str(config.TUTOR_ID)
    except ImportError:
        raise RuntimeError(
            "Не найдены BOT_TOKEN и TUTOR_ID ни в переменных окружения, ни в config.py!"
        )

TUTOR_ID = int(TUTOR_ID_RAW)

router = Router()


class BookingStates(StatesGroup):
    waiting_subject = State()
    waiting_grade = State()
    waiting_goal = State()
    waiting_contact = State()


class HomeworkStates(StatesGroup):
    waiting_subject = State()
    waiting_content = State()


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Записаться на занятие", callback_data="book_start")],
            [InlineKeyboardButton(text="Сдать домашнее задание", callback_data="hw_start")],
            [InlineKeyboardButton(text="Формулы и шпаргалки", callback_data="cheat_menu")],
        ]
    )


def subjects_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Математика", callback_data=f"{prefix}:Математика"),
                InlineKeyboardButton(text="Физика", callback_data=f"{prefix}:Физика"),
            ],
            [InlineKeyboardButton(text="Назад в меню", callback_data="back_menu")],
        ]
    )


def grades_kb() -> InlineKeyboardMarkup:
    grades = ["5", "6", "7", "8", "9", "10", "11"]
    rows = [
        [InlineKeyboardButton(text=f"{g} класс", callback_data=f"grade:{g}") for g in grades[:4]],
        [InlineKeyboardButton(text=f"{g} класс", callback_data=f"grade:{g}") for g in grades[4:]],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def goals_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтянуть оценки / текущая тема", callback_data="goal:Оценки и база")],
            [InlineKeyboardButton(text="Подготовка к ЦЭ / ЦТ", callback_data="goal:ЦЭ / ЦТ")],
            [InlineKeyboardButton(text="Контрольная / самостоятельная", callback_data="goal:Контрольная")],
        ]
    )


CHEAT_SHEETS: dict[str, tuple[str, str]] = {
    "math_alg": (
        "Математика: ФСУ и степени",
        "<b>Формулы сокращённого умножения:</b>\n"
        "• (a + b)² = a² + 2ab + b²\n"
        "• (a − b)² = a² − 2ab + b²\n"
        "• a² − b² = (a − b)(a + b)\n\n"
        "<b>Степени (при a ≠ 0):</b>\n"
        "• aⁿ · aᵐ = aⁿ⁺ᵐ\n"
        "• aⁿ : aᵐ = aⁿ⁻ᵐ\n"
        "• (aⁿ)ᵐ = aⁿᵐ\n"
        "• a⁰ = 1,  a⁻ⁿ = 1 / aⁿ",
    ),
    "math_geom": (
        "Математика: Геометрия и прогрессии",
        "<b>Площади и периметр:</b>\n"
        "• Прямоугольник: S = a · b,  P = 2(a + b)\n"
        "• Треугольник: S = ½ · a · h\n"
        "• Окружность и круг: C = 2πr,  S = πr²\n"
        "• Теорема Пифагора: c² = a² + b²\n\n"
        "<b>Арифметическая прогрессия:</b>\n"
        "• aₙ = a₁ + d(n − 1)\n"
        "• Sₙ = ((a₁ + aₙ) / 2) · n",
    ),
    "phys_mech": (
        "Физика: Механика и плотность",
        "<b>Движение и сила:</b>\n"
        "• Скорость при равномерном движении: v = S / t\n"
        "• Плотность: ρ = m / V\n"
        "• Сила тяжести: F = m · g  (g ≈ 9,8–10 Н/кг)\n"
        "• Второй закон Ньютона: F = m · a\n"
        "• Давление твёрдого тела: p = F / S",
    ),
    "phys_elec": (
        "Физика: Электричество и работа",
        "<b>Постоянный ток и работа:</b>\n"
        "• Закон Ома для участка цепи: I = U / R\n"
        "• Мощность тока: P = U · I\n"
        "• Работа тока: A = U · I · t\n"
        "• Механическая работа: A = F · S · cos α\n"
        "• Кинетическая энергия: Eₖ = (m · v²) / 2",
    ),
}


def cheat_subjects_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Математика", callback_data="cheat_subj:math"),
                InlineKeyboardButton(text="Физика", callback_data="cheat_subj:phys"),
            ],
            [InlineKeyboardButton(text="Назад в меню", callback_data="back_menu")],
        ]
    )


def cheat_topics_kb(subj: str) -> InlineKeyboardMarkup:
    if subj == "math":
        rows = [
            [InlineKeyboardButton(text="ФСУ и степени", callback_data="cheat_show:math_alg")],
            [InlineKeyboardButton(text="Геометрия и прогрессии", callback_data="cheat_show:math_geom")],
        ]
    else:
        rows = [
            [InlineKeyboardButton(text="Механика и плотность", callback_data="cheat_show:phys_mech")],
            [InlineKeyboardButton(text="Электричество и работа", callback_data="cheat_show:phys_elec")],
        ]

    rows.append([InlineKeyboardButton(text="К выбору предмета", callback_data="cheat_menu")])
    rows.append([InlineKeyboardButton(text="В главное меню", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cheat_back_kb(topic_key: str) -> InlineKeyboardMarkup:
    subj = "math" if topic_key.startswith("math_") else "phys"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Другие темы предмета", callback_data=f"cheat_subj:{subj}")],
            [InlineKeyboardButton(text="В главное меню", callback_data="back_menu")],
        ]
    )

@router.message(CommandStart())
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "Активных действий нет. Выберите пункт в меню:",
            reply_markup=main_menu_kb(),
        )
        return

    await state.clear()
    await message.answer(
        "Действие отменено. Возвращаю в главное меню:",
        reply_markup=main_menu_kb(),
    )
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Это бот репетитора по математике и физике (5–11 классы).\n"
        "Выберите нужное действие:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "back_menu")
async def back_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "Главное меню. Выберите действие:",
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


# --- СЦЕНАРИЙ 1: ЗАПИСЬ НА ЗАНЯТИЕ ---
@router.callback_query(F.data == "book_start")
async def book_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingStates.waiting_subject)
    await callback.message.edit_text(
        "Выберите предмет:",
        reply_markup=subjects_kb("book_subj"),
    )
    await callback.answer()


@router.callback_query(F.data == "cheat_menu")
async def cheat_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "<b>Формулы и шпаргалки</b>\nВыберите предмет:",
        parse_mode="HTML",
        reply_markup=cheat_subjects_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cheat_subj:"))
async def cheat_subj(callback: CallbackQuery) -> None:
    subj = callback.data.split(":", 1)[1]
    title = "Математика" if subj == "math" else "Физика"
    await callback.message.edit_text(
        f"<b>{title}</b> — выберите раздел:",
        parse_mode="HTML",
        reply_markup=cheat_topics_kb(subj),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cheat_show:"))
async def cheat_show(callback: CallbackQuery) -> None:
    topic_key = callback.data.split(":", 1)[1]
    item = CHEAT_SHEETS.get(topic_key)
    if not item:
        await callback.answer("Раздел не найден", show_alert=True)
        return

    title, body = item
    await callback.message.edit_text(
        f"<b>{title}</b>\n\n{body}",
        parse_mode="HTML",
        reply_markup=cheat_back_kb(topic_key),
    )
    await callback.answer()
    
@router.callback_query(BookingStates.waiting_subject, F.data.startswith("book_subj:"))
async def book_subject(callback: CallbackQuery, state: FSMContext) -> None:
    subject = callback.data.split(":", 1)[1]
    await state.update_data(subject=subject)
    await state.set_state(BookingStates.waiting_grade)
    await callback.message.edit_text(
        f"Предмет: <b>{subject}</b>\nВыберите класс:",
        parse_mode="HTML",
        reply_markup=grades_kb(),
    )
    await callback.answer()


@router.callback_query(BookingStates.waiting_grade, F.data.startswith("grade:"))
async def book_grade(callback: CallbackQuery, state: FSMContext) -> None:
    grade = callback.data.split(":", 1)[1]
    await state.update_data(grade=grade)
    await state.set_state(BookingStates.waiting_goal)
    await callback.message.edit_text(
        f"Класс: <b>{grade}</b>\nКакая основная цель?",
        parse_mode="HTML",
        reply_markup=goals_kb(),
    )
    await callback.answer()


@router.callback_query(BookingStates.waiting_goal, F.data.startswith("goal:"))
async def book_goal(callback: CallbackQuery, state: FSMContext) -> None:
    goal = callback.data.split(":", 1)[1]
    await state.update_data(goal=goal)
    await state.set_state(BookingStates.waiting_contact)
    await callback.message.edit_text(
        "Напишите имя, удобные дни/время и контакт для связи (телефон или @username):"
    )
    await callback.answer()


@router.message(BookingStates.waiting_contact, ~F.text)
async def book_contact_not_text(message: Message) -> None:
    await message.answer(
        "Пожалуйста, напишите имя, удобные дни/время и контакт для связи текстом "
        "(фото, стикеры и голосовые на этом шаге не подходят).\n"
        "Если передумали — отправьте /cancel."
    )


@router.message(BookingStates.waiting_contact, F.text)
async def book_finish(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    user_link = f"@{message.from_user.username}" if message.from_user.username else f"ID {message.from_user.id}"

    tutor_text = (
        "<b>Новая заявка на занятие!</b>\n"
        f"• Предмет: {data.get('subject')}\n"
        f"• Класс: {data.get('grade')}\n"
        f"• Цель: {data.get('goal')}\n"
        f"• От: {message.from_user.full_name} ({user_link})\n"
        f"• Детали: {message.text}"
    )

    await bot.send_message(chat_id=TUTOR_ID, text=tutor_text, parse_mode="HTML")
    await state.clear()
    await message.answer(
        "Заявка отправлена! Репетитор свяжется с вами в ближайшее время.",
        reply_markup=main_menu_kb(),
    )


# --- СЦЕНАРИЙ 2: СДАЧА ДОМАШНЕГО ЗАДАНИЯ ---
@router.callback_query(F.data == "hw_start")
async def hw_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(HomeworkStates.waiting_subject)
    await callback.message.edit_text(
        "По какому предмету сдаете домашнее задание?",
        reply_markup=subjects_kb("hw_subj"),
    )
    await callback.answer()


@router.callback_query(HomeworkStates.waiting_subject, F.data.startswith("hw_subj:"))
async def hw_subject(callback: CallbackQuery, state: FSMContext) -> None:
    subject = callback.data.split(":", 1)[1]
    await state.update_data(hw_subject=subject)
    await state.set_state(HomeworkStates.waiting_content)
    await callback.message.edit_text(
        f"Предмет: <b>{subject}</b>\n"
        "Отправьте фото решения или напишите текст/вопрос по задаче (можно добавить комментарий):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(HomeworkStates.waiting_content)
async def hw_finish(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    subject = data.get("hw_subject", "Не указан")
    user_link = f"@{message.from_user.username}" if message.from_user.username else f"ID {message.from_user.id}"
    caption_text = message.caption or message.text or "Без комментария"

    header = (
        "<b>Новое ДЗ от ученика!</b>\n"
        f"• Предмет: {subject}\n"
        f"• Ученик: {message.from_user.full_name} ({user_link})\n"
        f"• Комментарий/текст: {caption_text}"
    )

    if message.photo:
        photo_id = message.photo[-1].file_id
        await bot.send_photo(chat_id=TUTOR_ID, photo=photo_id, caption=header, parse_mode="HTML")
    elif message.document:
        await bot.send_document(
            chat_id=TUTOR_ID,
            document=message.document.file_id,
            caption=header,
            parse_mode="HTML",
        )
    else:
        await bot.send_message(chat_id=TUTOR_ID, text=header, parse_mode="HTML")

    await state.clear()
    await message.answer(
        "Домашнее задание отправлено репетитору!",
        reply_markup=main_menu_kb(),
    )


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())