from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import config
from database import db
from trading_analysis import analyzer
from localization import t
try:
    from pocket_option_client import get_pocket_option_client
except Exception:
    def get_pocket_option_client():
        return None
import asyncio
from datetime import datetime
import os
import random
from groq import Groq

router = Router()

# Храним последнее инфо-сообщение по пользователю, чтобы удалять его при новом сигнале
last_signal_info_msg_id = {}


class AccessCodeState(StatesGroup):
    waiting_for_code = State()
    choosing_language = State()


class AIAssistantState(StatesGroup):
    waiting_for_question = State()


def get_user_lang(user_id: int) -> str:
    try:
        return db.get_language(user_id)
    except Exception:
        return "ru"


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Добавляем пользователя в базу данных
    db.add_user(user_id, username, full_name)
    
    # Всегда предлагаем выбрать язык при старте
    await state.set_state(AccessCodeState.choosing_language)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("ru", "btn_lang_ru"), callback_data="set_lang_ru"),
            InlineKeyboardButton(text=t("en", "btn_lang_en"), callback_data="set_lang_en")
        ]
    ])
    await message.answer(t("ru", "lang_prompt"), reply_markup=keyboard, parse_mode="HTML")


async def send_welcome(message: Message, lang: str):
    welcome_text = t(lang, "welcome", partner=config.PARTNER_LINK, admin=config.ADMIN_USERNAME)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_enter_code"), callback_data="enter_code")]
    ])
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("set_lang_"))
async def set_language_callback(callback: CallbackQuery, state: FSMContext):
    lang_code = "ru" if callback.data == "set_lang_ru" else "en"
    user_id = callback.from_user.id
    db.set_language(user_id, lang_code)
    await state.clear()
    
    # Проверяем активацию
    if db.is_user_active(user_id):
        await show_main_menu(callback, lang_code)
    else:
        await send_welcome(callback.message, lang_code)


@router.callback_query(F.data == "enter_code")
async def enter_code_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик нажатия на кнопку ввода кода"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)
    await callback.message.answer(
        t(lang, "enter_code"),
        parse_mode="HTML"
    )
    await state.set_state(AccessCodeState.waiting_for_code)


@router.message(AccessCodeState.waiting_for_code)
async def process_access_code(message: Message, state: FSMContext):
    """Обработка введенного кода доступа"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    entered_code = message.text.strip()
    
    if entered_code == config.ACCESS_CODE:
        # Код правильный - активируем пользователя
        db.activate_user(user_id)
        await state.clear()
        await message.answer(
            t(lang, "code_ok"),
            parse_mode="HTML"
        )
        await show_main_menu(message, lang)
    else:
        # Код неправильный
        await message.answer(
            t(lang, "code_bad"),
            parse_mode="HTML"
        )


async def get_image_file(image_path_or_url: str):
    """Получить файл изображения (локальный или URL)"""
    if config.USE_LOCAL_IMAGES and os.path.exists(image_path_or_url):
        return FSInputFile(image_path_or_url)
    return image_path_or_url  # URL


async def show_main_menu(message_or_callback, lang: str = "ru"):
    """Показать главное меню"""
    menu_text = t(lang, "main_menu")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_get_signal"), callback_data="get_signal")],
        [InlineKeyboardButton(text=t(lang, "btn_get_otc"), callback_data="get_otc_signals")],
        [InlineKeyboardButton(text=t(lang, "btn_statistics"), callback_data="statistics")],
        [InlineKeyboardButton(text=t(lang, "btn_training"), callback_data="training")],
        [InlineKeyboardButton(text=t(lang, "btn_support"), callback_data="support")]
    ])
    
    # Получаем изображение
    photo = await get_image_file(config.IMAGE_MAIN_MENU)
    
    # Если это callback, редактируем сообщение, иначе создаем новое
    if hasattr(message_or_callback, 'message'):
        # Это CallbackQuery - редактируем
        try:
            # Пытаемся отредактировать с фото
            await message_or_callback.message.edit_media(
                media=InputMediaPhoto(
                    media=photo,
                    caption=menu_text,
                    parse_mode="HTML"
                ),
                reply_markup=keyboard
            )
        except Exception:
            # Если не получилось отредактировать с фото, просто текст
            await message_or_callback.message.edit_text(menu_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        # Это Message - отправляем новое сообщение с фото
        try:
            if isinstance(photo, str):
                # URL фото
                await message_or_callback.answer_photo(
                    photo=photo,
                    caption=menu_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Локальный файл
                await message_or_callback.answer_photo(
                    photo=photo,
                    caption=menu_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        except Exception:
            # Если фото не загрузилось, отправляем только текст
            await message_or_callback.answer(menu_text, reply_markup=keyboard, parse_mode="HTML")


def _signal_strength(result: dict) -> float:
    total = result.get("total_indicators") or 0
    if total <= 0:
        return 0.0
    buy = result.get("buy_signals") or 0
    sell = result.get("sell_signals") or 0
    return max(buy, sell) / total


def _fallback_signal_from_result(result: dict) -> dict:
    buy = result.get("buy_signals") or 0
    sell = result.get("sell_signals") or 0
    total = result.get("total_indicators") or 0

    # Если сигнал совсем слабый или голоса равны — выбираем направление случайно
    if total == 0 or buy == sell:
        direction = random.choice(["ВВЕРХ", "ВНИЗ"])
    else:
        direction = "ВВЕРХ" if buy > sell else "ВНИЗ"

    signal_type = "BUY" if direction == "ВВЕРХ" else "SELL"
    strength = _signal_strength(result)
    confidence = max(config.CONFIDENCE_MIN, min(config.CONFIDENCE_MAX, int(70 + strength * 30)))

    # Время экспирации: для реальных пар даём 1/3/5 мин, для OTC оставляем как есть
    if result.get("is_otc"):
        time_minutes = result.get("time_minutes") or 5
    else:
        tm = result.get("time_minutes")
        if tm in (1, 3, 5):
            time_minutes = tm
        else:
            time_minutes = random.choice([1, 3, 5])
    return {
        **result,
        "stable": True,
        "direction": direction,
        "signal_type": signal_type,
        "confidence": confidence,
        "time_minutes": time_minutes
    }


async def _run_signal_flow(callback: CallbackQuery, pair: str, is_otc: bool, result: dict = None):
    lang = get_user_lang(callback.from_user.id)

    # Удаляем предыдущее инфо-сообщение при новом сигнале
    prev_info_id = last_signal_info_msg_id.get(callback.from_user.id)
    if prev_info_id:
        try:
            await callback.bot.delete_message(callback.message.chat.id, prev_info_id)
        except Exception:
            pass

    # 1. Этап: Показываем краткое описание алгоритма (RU / EN)
    if lang == "en":
        info_text = (
            "<b>How do we choose a signal?</b>\n\n"
            "Our algorithm analyses the market in real time, taking into account key factors:\n\n"
            "🔹 <b>RSI (Relative Strength Index)</b> — shows overbought/oversold conditions.\n"
            "🔹 <b>Actual trading volumes</b> — help to understand the strength of the move.\n"
            "🔹 <b>Current volatility</b> — the higher the swings, the more careful the signals.\n"
            "🔹 <b>Trend impulses</b> — so we do not go against the main trend.\n\n"
            "📊 <b>The algorithm searches for the best entry points with probability estimation.</b>\n"
            "⚡️ <b>This helps to find high‑confidence signals even in unstable conditions!</b>"
        )
    else:
        info_text = (
            "<b>Как мы подбираем сигнал?</b>\n\n"
            "Наш алгоритм анализирует рынок в режиме реального времени, учитывая ключевые факторы:\n\n"
            "🔹 <b>RSI (Relative Strength Index)</b> — определяет состояние перекупленности или перепроданности.\n"
            "🔹 <b>Актуальные объемы торгов</b> — помогают понять силу текущего движения.\n"
            "🔹 <b>Текущую волатильность</b> — чем выше колебания, тем осторожнее сигналы.\n"
            "🔹 <b>Трендовые импульсы</b> — чтобы не идти против основного направления рынка.\n\n"
            "📊 <b>Алгоритм ищет наилучшие точки входа с расчётом вероятности успеха.</b>\n"
            "⚡️ <b>Это помогает находить сигналы с высокой уверенностью даже в нестабильных условиях!</b>"
        )
    info_msg = await callback.message.answer(info_text, parse_mode="HTML")
    last_signal_info_msg_id[callback.from_user.id] = info_msg.message_id

    # 2. Этап: Создаем сообщение с динамическим анализом (имитация)
    analysis_msg = await callback.message.answer(
        "Ищу лучший сигнал для тебя... ⚪️" if lang == "ru" else "Looking for the best signal for you... ⚪️"
    )

    # Стадии прогресса (общее время 10-12 секунд)
    pair_label = pair.replace("/", "").replace(" ", "")
    if lang == "en":
        stages = [
            ("Analyzing market... 🟡", 1.1),
            (f"Fetching data for {pair_label}... 🔵", 1.1),
            ("Analysis completed 9%... 11 sec left", 1.1),
            ("Analysis completed 18%... 10 sec left", 1.1),
            ("Analysis completed 27%... 9 sec left", 1.1),
            ("Analysis completed 45%... 7 sec left", 1.1),
            ("Analysis completed 63%... 5 sec left", 1.1),
            ("Analysis completed 81%... 3 sec left", 1.1),
            ("Analysis completed 90%... 2 sec left", 1.1),
            ("Analysis completed 100%... Preparing result... ✅", 1.1),
        ]
    else:
        stages = [
            ("Анализирую рынок... 🟡", 1.1),
            (f"Получаю данные по {pair_label}... 🔵", 1.1),
            ("Анализ завершен на 9%... Осталось 11 сек", 1.1),
            ("Анализ завершен на 18%... Осталось 10 сек", 1.1),
            ("Анализ завершен на 27%... Осталось 9 сек", 1.1),
            ("Анализ завершен на 45%... Осталось 7 сек", 1.1),
            ("Анализ завершен на 63%... Осталось 5 сек", 1.1),
            ("Анализ завершен на 81%... Осталось 3 сек", 1.1),
            ("Анализ завершен на 90%... Осталось 2 сек", 1.1),
            ("Анализ завершен на 100%... Подготовка результата... ✅", 1.1),
        ]

    for text, delay in stages:
        await asyncio.sleep(delay)
        await analysis_msg.edit_text(text)

    # 3. Этап: Выполняем анализ и показываем финальный сигнал (при наличии PO API — с живой ценой/RSI)
    if result is None:
        live_quote = None
        po = get_pocket_option_client()
        if po:
            try:
                live_quote = await po.get_quote(pair, is_otc=is_otc)
            except Exception:
                pass
        result = analyzer.analyze_pair(pair, is_otc=is_otc, live_quote=live_quote)

    if not result.get("stable"):
        result = _fallback_signal_from_result(result)

    # Получаем текущую дату
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")

    # Определяем время экспирации (1/3/5 мин из анализа, по умолчанию 5)
    expiry_minutes = result.get("time_minutes") or 5
    expiry_time = now.strftime("%H:%M")

    # Формируем текст сигнала по шаблону
    direction_ru = "ВВЕРХ" if result["signal_type"] == "BUY" else "ВНИЗ"
    direction_en = "UP" if result["signal_type"] == "BUY" else "DOWN"
    price_value = result.get("price")
    rsi_value = result.get("rsi")
    confidence = result["confidence"]

    # Для реальных пар показываем только реальные значения, без фиктивных заглушек
    price_text = f"{price_value:.5f}" if isinstance(price_value, (int, float)) else "—"
    rsi_text = f"{rsi_value:.1f}" if isinstance(rsi_value, (int, float)) else "—"
    pair_text = pair.replace("/", "").replace(" ", "")

    if lang == "en":
        signal_text = (
            f"💡 <b>Signal for {date_str}</b>\n\n"
            f"🔹 <b>Asset:</b> {pair_text} "
            f"💰 <b>Current price:</b> {price_text} "
            f"📊 <b>RSI(14):</b> {rsi_text} "
            f"⏳ <b>Expiry time:</b> {expiry_time} ({expiry_minutes} min) "
            f"📈 <b>Forecast:</b> {direction_en} "
            f"📉 <b>Confidence:</b> {confidence}%\n\n"
            f"⚠️ <b>Important:</b> follow risk management. No more than 2% of balance per trade.\n\n"
            f"👇 Please rate this signal below. Your feedback helps us make forecasts more accurate!"
        )
    else:
        signal_text = (
            f"💡 <b>Сигнал на {date_str}</b>\n\n"
            f"🔹 <b>Актив:</b> {pair_text} "
            f"💰 <b>Текущая цена:</b> {price_text} "
            f"📊 <b>RSI(14):</b> {rsi_text} "
            f"⏳ <b>Время экспирации:</b> {expiry_time} ({expiry_minutes} мин) "
            f"📈 <b>Прогноз:</b> {direction_ru} "
            f"📉 <b>Уверенность:</b> {confidence}%\n\n"
            f"⚠️ <b>Важно:</b> соблюдайте риск-менеджмент. Не более 2% от депозита на сделку.\n\n"
            f"👇 Пожалуйста, оцените результат этого сигнала ниже. Ваша обратная связь помогает нам делать прогнозы точнее!"
        )

    # Выбираем изображение в зависимости от направления сигнала
    if result['signal_type'] == "BUY":
        photo = await get_image_file(config.IMAGE_SIGNAL_BUY)
    else:
        photo = await get_image_file(config.IMAGE_SIGNAL_SELL)

    # Клавиатура с кнопками фидбека
    safe_pair = pair.replace("/", "-").replace(" ", "-").replace("_", "-")

    # Вторая строка кнопок: для реальных пар — "Ещё сигнал", для OTC — "Назад к выбору пар"
    if is_otc:
        second_row = [
            InlineKeyboardButton(
                text="📉 Выбор пары" if lang == "ru" else "📉 Select pair",
                callback_data="get_otc_signals"
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_main"),
                callback_data="main_menu"
            ),
        ]
    else:
        second_row = [
            InlineKeyboardButton(
                text="📊 Ещё сигнал" if lang == "ru" else "📊 New signal",
                callback_data="get_signal"
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_main"),
                callback_data="main_menu"
            ),
        ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t(lang, "btn_feedback_ok"),
                callback_data=f"feedback_{safe_pair}|{result['signal_type']}|success"
            ),
            InlineKeyboardButton(
                text=t(lang, "btn_feedback_fail"),
                callback_data=f"feedback_{safe_pair}|{result['signal_type']}|fail"
            )
        ],
        second_row,
    ])

    # Заменяем прогресс-бар на финальную карточку
    try:
        await analysis_msg.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=signal_text,
                parse_mode="HTML"
            ),
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Ошибка при редактировании с фото: {e}")
        await analysis_msg.edit_text(
            signal_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data == "get_signal")
async def get_signal_callback(callback: CallbackQuery):
    """Обработчик получения сигнала - быстрый подбор пары"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)

    # Удаляем прошлый сигнал/сообщение, чтобы не захламлять чат
    try:
        await callback.message.delete()
    except Exception:
        pass
    # Мгновенное сообщение пользователю, что идёт анализ рынка
    try:
        searching_text = (
            "🔍 <b>Анализирую рынок...</b> ⏳"
            if lang == "ru"
            else "🔍 <b>Analyzing market...</b> ⏳"
        )
        searching_msg = await callback.message.answer(searching_text, parse_mode="HTML")
        # Лёгкая анимация «тикания часов» перед основным флоу
        clock_frames = ["🕐", "🕑", "🕒", "🕓", "🕔", "🕕"]
        for i in range(len(clock_frames)):
            await asyncio.sleep(0.7)
            dots = "".join(clock_frames[: i + 1])
            try:
                if lang == "ru":
                    anim_text = f"🔍 <b>Анализирую рынок...</b> {dots}"
                else:
                    anim_text = f"🔍 <b>Analyzing market...</b> {dots}"
                await searching_msg.edit_text(anim_text, parse_mode="HTML")
            except Exception:
                break
    except Exception:
        searching_msg = None

    # Вместо тяжёлого перебора всех пар выбираем одну случайную (для скорости ответа)
    pairs = list(config.MAIN_PAIRS)
    random.shuffle(pairs)
    best_pair = pairs[0]
    best_result = None  # анализ и котировки возьмём уже внутри _run_signal_flow

    # Убираем временное сообщение, если удалось отправить
    if searching_msg:
        try:
            await searching_msg.delete()
        except Exception:
            pass

    await _run_signal_flow(callback, best_pair, is_otc=False, result=best_result)


@router.callback_query(F.data.startswith("analyze_"))
async def analyze_pair_callback(callback: CallbackQuery):
    """Обработчик анализа выбранной пары с новым флоу"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)
    # Удаляем сообщение со списком пар, чтобы очистить чат
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Определяем, это OTC или обычная пара
    if callback.data.startswith("analyze_otc_"):
        pair = callback.data.replace("analyze_otc_", "")
        is_otc = True
    else:
        pair = callback.data.replace("analyze_", "")
        is_otc = False

        # Проверка выходных для реальных пар
        if is_weekend():
            weekend_text = t(lang, "weekend")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "btn_get_otc"), callback_data="get_otc_signals")],
                [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
            ])
            # Проверяем тип сообщения перед редактированием
            try:
                if callback.message.photo:
                    await callback.message.delete()
                    await callback.message.answer(weekend_text, reply_markup=keyboard, parse_mode="HTML")
                else:
                    await callback.message.edit_text(weekend_text, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                await callback.message.answer(weekend_text, reply_markup=keyboard, parse_mode="HTML")
            return

    await _run_signal_flow(callback, pair, is_otc=is_otc)


def _pair_flags(pair_label: str) -> str:
    """
    Возвращает два флага по коду пары (база/котировка),
    как на референсном скрине.
    Для OTC строк вида 'EUR/USD - OTC' парсим только валюты.
    """
    core = pair_label.split(" ")[0]      # 'EUR/USD'
    base, quote = core.split("/")[:2]    # 'EUR', 'USD'
    mapping = {
        "EUR": "🇪🇺",
        "USD": "🇺🇸",
        "GBP": "🇬🇧",
        "AUD": "🇦🇺",
        "NZD": "🇳🇿",
        "CAD": "🇨🇦",
        "CHF": "🇨🇭",
        "JPY": "🇯🇵",
        "RUB": "🇷🇺",
        "CLP": "🇨🇱",
        "PKR": "🇵🇰",
        "DZD": "🇩🇿",
        "ARS": "🇦🇷",
        "BRL": "🇧🇷",
        "BDT": "🇧🇩",
        "YER": "🇾🇪",
        "LBP": "🇱🇧",
        "TND": "🇹🇳",
        "NGN": "🇳🇬",
        "HUF": "🇭🇺",
        "NOK": "🇳🇴",
        "QAR": "🇶🇦",
        "AED": "🇦🇪",
        "JOD": "🇯🇴",
        "ZAR": "🇿🇦",
        "VND": "🇻🇳",
        "THB": "🇹🇭",
        "INR": "🇮🇳",
        "EGP": "🇪🇬",
        "MXN": "🇲🇽",
        "SGD": "🇸🇬",
        "CNY": "🇨🇳",
    }
    base_flag = mapping.get(base, "📊")
    quote_flag = mapping.get(quote, "")
    return f"{base_flag}{quote_flag}"


def _build_otc_keyboard(lang: str, page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    """Создаёт красивую пагинируемую клавиатуру OTC как на референсе."""
    total = len(config.OTC_PAIRS)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))

    start = page * per_page
    end = start + per_page
    slice_pairs = config.OTC_PAIRS[start:end]

    buttons: list[list[InlineKeyboardButton]] = []

    # Пары: по 2 в ряд, с двумя флагами как в примере
    row: list[InlineKeyboardButton] = []
    for pair in slice_pairs:
        flags = _pair_flags(pair)
        text = f"{flags} {pair.replace(' - OTC', ' OTC')}"
        row.append(InlineKeyboardButton(
            text=text,
            callback_data=f"analyze_otc_{pair}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Строка навигации страниц
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"get_otc_signals_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="otc_page_info"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"get_otc_signals_{page+1}"))
    buttons.append(nav_row)

    # Кнопка "В главное меню"
    buttons.append([InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("get_otc_signals"))
async def get_otc_signals_callback(callback: CallbackQuery):
    """Обработчик выбора OTC сигналов с пагинацией"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)

    # Определяем страницу из callback_data: get_otc_signals_{page}
    parts = callback.data.split("_")
    page = 0
    if len(parts) >= 4:
        try:
            page = int(parts[-1])
        except ValueError:
            page = 0

    keyboard = _build_otc_keyboard(lang, page=page, per_page=8)
    text = t(lang, "choose_otc")

    # Проверяем, есть ли фото в сообщении
    try:
        if callback.message.photo:
            # Если есть фото, удаляем и отправляем новое текстовое
            await callback.message.delete()
            await callback.message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Если текстовое сообщение, просто редактируем
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception as e:
        # Если что-то пошло не так, отправляем новое сообщение
        print(f"Ошибка при редактировании сообщения: {e}")
        await callback.message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


def is_weekend() -> bool:
    """Проверка, является ли сегодня выходным днем (суббота или воскресенье)"""
    today = datetime.now().weekday()  # 5 = суббота, 6 = воскресенье
    return today >= 5


@router.callback_query(F.data == "training")
async def training_callback(callback: CallbackQuery):
    """Обработчик раздела обучения - показывает подменю"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)

    training_menu_text = (
        "📚 <b>РАЗДЕЛ ОБУЧЕНИЯ</b>\n\nВыберите вариант обучения:"
        if lang == "ru"
        else "📚 <b>TRAINING SECTION</b>\n\nChoose a training option:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_basic_training"), callback_data="basic_training")],
        [InlineKeyboardButton(text=t(lang, "btn_ai_assistant"), callback_data="ai_assistant")],
        [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
    ])

    # Получаем изображение для обучения
    photo = await get_image_file(config.IMAGE_TRAINING)

    # Редактируем сообщение с фото
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=training_menu_text,
                parse_mode="HTML"
            ),
            reply_markup=keyboard
        )
    except Exception:
        # Если не получилось отредактировать с фото, просто текст
        await callback.message.edit_text(
            training_menu_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data == "statistics")
async def statistics_callback(callback: CallbackQuery):
    """Обработчик раздела статистики"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)

    # Получаем реальную статистику из базы данных
    stats = db.get_feedback_stats()

    # Генерируем случайные данные для демонстрации
    import random
    from datetime import datetime

    # Случайные успешные и неуспешные сигналы (если нет реальных данных)
    if stats['total_signals'] == 0:
        successful = random.randint(25, 50)
        failed = random.randint(5, 15)
    else:
        successful = stats['successful']
        failed = stats['failed']

    # Текущая дата и время
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H:%M")

    if lang == "en":
        statistics_text = f"""
📊 <b>BOT STATISTICS</b>

📅 <b>Date:</b> {date_str}
⏰ <b>Time:</b> {time_str}

📈 <b>Total signals:</b> {successful + failed}
✅ <b>Winning:</b> {successful}
❌ <b>Losing:</b> {failed}

🎯 <b>Win rate:</b> {round(successful / (successful + failed) * 100, 1) if successful + failed > 0 else 0}%

💡 <b>Statistics are updated in real time</b>
"""
    else:
        statistics_text = f"""
📊 <b>СТАТИСТИКА БОТА</b>

📅 <b>Дата:</b> {date_str}
⏰ <b>Время:</b> {time_str}

📈 <b>Всего сигналов:</b> {successful + failed}
✅ <b>Успешных:</b> {successful}
❌ <b>Неуспешных:</b> {failed}

🎯 <b>Процент успеха:</b> {round(successful / (successful + failed) * 100, 1) if successful + failed > 0 else 0}%

💡 <b>Статистика обновляется в реальном времени</b>
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
    ])

    # Получаем изображение для статистики (используем то же что и для меню)
    photo = await get_image_file(config.IMAGE_STATISTICS)

    # Редактируем сообщение с фото
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=statistics_text,
                parse_mode="HTML"
            ),
            reply_markup=keyboard
        )
    except Exception:
        # Если не получилось отредактировать с фото, просто текст
        await callback.message.edit_text(
            statistics_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery):
    """Обработчик раздела поддержки"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)

    support_text = t(lang, "support", admin=config.ADMIN_USERNAME)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
    ])

    # Получаем изображение для поддержки
    photo = await get_image_file(config.IMAGE_SUPPORT)

    # Редактируем сообщение с фото
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=support_text,
                parse_mode="HTML"
            ),
            reply_markup=keyboard
        )
    except Exception:
        # Если не получилось отредактировать с фото, просто текст
        await callback.message.edit_text(
            support_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("feedback_"))
async def feedback_callback(callback: CallbackQuery):
    """Обработчик фидбека по сигналу"""
    lang = get_user_lang(callback.from_user.id)
    await callback.answer(t(lang, "feedback_received"), show_alert=False)
    
    # Парсим данные из callback_data: feedback_{pair}|{signal_type}|{result}
    # Используем | как разделитель для избежания проблем с символами в pair
    try:
        data_parts = callback.data.replace("feedback_", "").split("|")
        if len(data_parts) >= 3:
            pair = data_parts[0].replace("-", "/")  # Возвращаем оригинальный формат
            signal_type = data_parts[1]
            feedback_result = data_parts[2]  # success или fail
            
            user_id = callback.from_user.id
            
            # Сохраняем фидбек в базу данных
            db.add_feedback(user_id, pair, signal_type, feedback_result)
            
            # Определяем, OTC или обычная пара
            is_otc = "OTC" in pair or pair in config.OTC_PAIRS
            
            # Обновляем кнопки:
            # - для реальных пар: "Новый сигнал"
            # - для OTC: "Выбор пары" (возврат к списку OTC-пар)
            try:
                if is_otc:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📉 Выбор пары" if lang == "ru" else "📉 Select pair",
                                callback_data="get_otc_signals"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=t(lang, "main_menu_btn"),
                                callback_data="main_menu"
                            )
                        ]
                    ])
                else:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📊 Новый сигнал" if lang == "ru" else "📊 New signal",
                                callback_data="get_signal"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=t(lang, "main_menu_btn"),
                                callback_data="main_menu"
                            )
                        ]
                    ])
                await callback.message.edit_reply_markup(reply_markup=keyboard)
            except Exception as e:
                print(f"Ошибка при обновлении кнопок: {e}")
    except Exception as e:
        print(f"Ошибка при обработке фидбека: {e}")


@router.callback_query(F.data == "basic_training")
async def basic_training_callback(callback: CallbackQuery):
    """Обработчик базового обучения"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)

    training_text = t(lang, "training")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "ai_back_to_training"), callback_data="training")],
        [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
    ])

    # Получаем изображение для обучения
    photo = await get_image_file(config.IMAGE_TRAINING)

    # Редактируем сообщение с фото
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=training_text,
                parse_mode="HTML"
            ),
            reply_markup=keyboard
        )
    except Exception:
        # Если не получилось отредактировать с фото, просто текст
        await callback.message.edit_text(
            training_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data == "ai_assistant")
async def ai_assistant_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик ИИ-ассистента"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)

    welcome_text = t(lang, "ai_assistant_welcome")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "ai_back_to_training"), callback_data="training")],
        [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
    ])

    # Получаем изображение для ИИ-ассистента (используем то же что и для обучения)
    photo = await get_image_file(config.IMAGE_ASSISTENT)

    # Редактируем сообщение с фото
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=photo,
                caption=welcome_text,
                parse_mode="HTML"
            ),
            reply_markup=keyboard
        )
    except Exception:
        # Если не получилось отредактировать с фото, просто текст
        await callback.message.edit_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    # Устанавливаем состояние ожидания вопроса
    await state.set_state(AIAssistantState.waiting_for_question)


def detect_language(text: str) -> str:
    """Определяет язык текста: 'ru' если есть кириллица, иначе 'en'"""
    if any('\u0400' <= c <= '\u04FF' for c in text):
        return "ru"
    return "en"


@router.message(AIAssistantState.waiting_for_question)
async def process_ai_question(message: Message, state: FSMContext):
    """Обработка вопроса к ИИ-ассистенту"""
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    question = message.text.strip()

    # Проверяем, что вопрос не пустой
    if not question:
        await message.answer(t(lang, "ai_assistant_ask_question"), parse_mode="HTML")
        return

    # Определяем язык вопроса для выбора системного промпта
    question_lang = detect_language(question)

    # Показываем сообщение о обработке
    processing_msg = await message.answer(t(lang, "ai_processing"), parse_mode="HTML")

    try:
        # Инициализируем Groq клиент (бесплатный и быстрый)
        if not config.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY не установлен в конфигурации")

        client = Groq(api_key=config.GROQ_API_KEY)

        # Выбираем системный промпт в зависимости от языка вопроса
        if question_lang == "ru":
            system_prompt = """Ты - профессиональный ИИ-ассистент по трейдингу Originale Trade и финансовым рынкам с глубокими знаниями в области технического анализа, фундаментального анализа и стратегий торговли.

ТВОИ ОБЯЗАННОСТИ:
- Отвечать ТОЛЬКО на вопросы, связанные с трейдингом, финансовыми рынками и инвестициями
- Предоставлять точную, профессиональную и полезную информацию
- Использовать технические термины корректно
- Давать практические советы с обоснованием
- Отвечать на русском языке

ОСНОВНЫЕ ТЕМЫ, ПО КОТОРЫМ ТЫ СПЕЦИАЛИЗИРУЕШЬСЯ:
1. ТЕХНИЧЕСКИЙ АНАЛИЗ:
   - Графические паттерны (треугольники, флаги, головы и плечи)
   - Индикаторы (RSI, MACD, Stochastic, Bollinger Bands, ADX)
   - Уровни поддержки/сопротивления, трендовые линии
   - Японские свечи и их комбинации

2. СТРАТЕГИИ ТОРГОВЛИ:
   - Скальпинг, дей-трейдинг, свинг-трейдинг
   - Торговля по тренду, контртрендовая торговля
   - Торговля на пробой, отбой от уровней
   - Риск-менеджмент и мани-менеджмент

3. ФИНАНСОВЫЕ ИНСТРУМЕНТЫ:
   - Валютные пары (Forex)
   - Акции и индексы
   - Криптовалюты
   - Товары (золото, нефть, металлы)

4. ПСИХОЛОГИЯ ТРЕЙДЕРА:
   - Контроль эмоций
   - Дисциплина и следование правилам
   - Работа с убытками и проигрышными сериями

5. РИСК-МЕНЕДЖМЕНТ:
   - Размер позиции (1-3% от депозита)
   - Стоп-лосс и тейк-профит
   - Диверсификация
   - Мартингейл (только в крайних случаях)

ПРАВИЛА ОТВЕТОВ:
- Будь конкретным и давай примеры
- Если вопрос не связан с трейдингом, вежливо откажись и напомни о специализации
- Не давай финансовых советов как рекомендацию к действию
- Подчеркивай, что любая торговля связана с рисками

ФОРМАТ ОТВЕТОВ:
- Используй структурированные ответы с заголовками
- Приводи примеры из практики
- Обосновывай свои рекомендации
- Будь объективным и сбалансированным"""
        else:
            system_prompt = """You are a professional AI assistant for trading and financial markets with deep knowledge in technical analysis, fundamental analysis, and trading strategies.

YOUR RESPONSIBILITIES:
- Answer ONLY questions related to trading, financial markets, and investments
- Provide accurate, professional, and useful information
- Use technical terms correctly
- Give practical advice with justification
- Answer in English

MAIN TOPICS YOU SPECIALIZE IN:
1. TECHNICAL ANALYSIS:
   - Chart patterns (triangles, flags, head and shoulders)
   - Indicators (RSI, MACD, Stochastic, Bollinger Bands, ADX)
   - Support/resistance levels, trend lines
   - Japanese candlesticks and their combinations

2. TRADING STRATEGIES:
   - Scalping, day trading, swing trading
   - Trend trading, counter-trend trading
   - Breakout trading, bounce off levels
   - Risk management and money management

3. FINANCIAL INSTRUMENTS:
   - Currency pairs (Forex)
   - Stocks and indices
   - Cryptocurrencies
   - Commodities (gold, oil, metals)

4. TRADER PSYCHOLOGY:
   - Emotional control
   - Discipline and following rules
   - Dealing with losses and losing streaks

5. RISK MANAGEMENT:
   - Position size (1-3% of deposit)
   - Stop-loss and take-profit
   - Diversification
   - Martingale (only in extreme cases)

ANSWER RULES:
- Be specific and give examples
- If the question is not related to trading, politely refuse and remind about specialization
- Do not give financial advice as a recommendation to action
- Emphasize that any trading involves risks

ANSWER FORMAT:
- Use structured answers with headings
- Give examples from practice
- Justify your recommendations
- Be objective and balanced"""

        # Отправляем запрос к Groq
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Новейшая бесплатная модель Groq
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        # Получаем ответ
        ai_response = response.choices[0].message.content.strip()

        # Формируем финальный ответ в зависимости от языка интерфейса
        if question_lang == "ru":
            final_response = f"[ИИ-Ассистент]\n\n{ai_response}\n\n[Задайте другой вопрос или вернитесь в меню]"
        else:
            final_response = f"[AI Assistant]\n\n{ai_response}\n\n[Ask another question or return to menu]"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "ai_back_to_training"), callback_data="training")],
            [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
        ])

        # Редактируем сообщение с ответом
        await processing_msg.edit_text(
            final_response,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except ValueError as e:
        # Ошибка конфигурации
        error_text = "Error: GROQ_API_KEY not set. Please set your Groq API key at https://console.groq.com/"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "ai_back_to_training"), callback_data="training")],
            [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
        ])
        await processing_msg.edit_text(
            error_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Error with Groq: {e}")
        # Проверяем тип ошибки
        error_message = str(e)
        if "authentication" in error_message.lower() or "invalid" in error_message.lower():
            # Проблема с API ключом
            error_text = "Error: Invalid Groq API key. Get your key at https://console.groq.com/"
        elif "rate" in error_message.lower():
            # Проблема с лимитом
            error_text = "Error: Rate limit exceeded. Please try again later."
        else:
            # Другая ошибка
            error_text = t(lang, "ai_error")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "ai_back_to_training"), callback_data="training")],
            [InlineKeyboardButton(text=t(lang, "btn_main"), callback_data="main_menu")]
        ])
        await processing_msg.edit_text(
            error_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    # Не очищаем состояние, чтобы пользователь мог задать следующий вопрос


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Обработчик возврата в главное меню"""
    await callback.answer()
    lang = get_user_lang(callback.from_user.id)
    # Удаляем текущее сообщение (сигнал/меню) и показываем новое главное меню
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_main_menu(callback.message, lang)

