import asyncio
import os
import asyncpg
import re
import aiohttp
from aiohttp import web
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

DB_URL = "postgresql://postgres:221221poN!_123@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"options=-c%20search_path%3Dpublic"

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN") # ЗАМЕНИ НА НОВЫЙ!
GROUP_ID = -1003732391540
THREAD_ID = 4122
ADMINS = [7848102369, 7516819824, 7009639495, 801666895, 5757255404, 5114472835, 8635156198, 6218212222, 8043402907]
CHIEF_ADMINS = [7516819824, 6218212222, 5114472835, 801666895]

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class Form(StatesGroup):
    # Состояния для жалобы на игрока
    comp_target_nick = State()
    comp_violation = State()
    comp_proofs = State()
    comp_user_nick = State()
    
    # Состояния для апелляции
    app_place = State()
    app_user_nick = State()
    app_reason = State()
    app_why_unban = State()

    # --- ВОТ ЭТИХ СТРОК У ТЕБЯ НЕ ХВАТАЕТ ---
    adm_comp_target = State()  # Тот самый, на который ругается ошибка
    adm_comp_text = State()
    adm_comp_proofs = State()
    # ----------------------------------------

    # Остальные состояния
    search_rb = State()
    ban_nick = State()
    ban_time = State()
    ban_reason = State()
    unban_nick = State()
    check_nick = State()
    admin_complaint = State()
    admin_feedback = State()
    
# --- ROBLOX API ---
async def get_roblox_data(username: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [username]}) as r1:
                data = await r1.json()
                if not data.get('data'): return None
                user_id = data['data'][0]['id']
                full_name = data['data'][0]['name']

            async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as r2:
                info = await r2.json()
                reg_date = info.get('created', 'Невідомо')[:10]

            async with session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png&isCircular=false") as r3:
                thumb_data = await r3.json()
                photo_url = thumb_data['data'][0]['imageUrl'] if thumb_data.get('data') else None

            return {"id": user_id, "name": full_name, "reg": reg_date, "photo": photo_url}
        except:
            return None

# --- КЛАВИАТУРЫ ---
def main_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    # Новая кнопка
    builder.row(types.InlineKeyboardButton(text="📖 Як використовувати бота", callback_data="btn_guide"))
    
    builder.row(types.InlineKeyboardButton(text="🔍 Пошук RB", callback_data="btn_search"))
    builder.row(types.InlineKeyboardButton(text="🚫 Перевірити бан", callback_data="btn_check_ban"))
    builder.row(types.InlineKeyboardButton(text="📝 Скарга на гравця", callback_data="btn_complaint"))
    builder.row(types.InlineKeyboardButton(text="⚖️ Апеляція", callback_data="btn_appeal"))
    builder.row(types.InlineKeyboardButton(text="👨‍✈️ Скарга на адміна", callback_data="btn_adm_complaint"))
    
    if user_id in ADMINS:
        builder.row(types.InlineKeyboardButton(text="🔨 Бан", callback_data="admin_ban"))
        builder.row(types.InlineKeyboardButton(text="🔓 Розбан", callback_data="admin_unban"))
    return builder.as_markup()

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    await message.answer(f"👋 Вітаємо!\nВаш ID: `{uid}`", reply_markup=main_kb(uid), parse_mode="Markdown")

# --- ЛОГИКА ПОИСКА RB ---
@dp.callback_query(F.data == "btn_search")
async def search_rb_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔎 Введіть точний нік гравця Roblox:")
    await state.set_state(Form.search_rb)
    await callback.answer()

@dp.message(Form.search_rb)
async def search_rb_proc(message: types.Message, state: FSMContext):
    if not message.text: return
    data = await get_roblox_data(message.text)
    if data:
        text = f"👤 Нік: `{data['name']}`\n🆔 ID: `{data['id']}`\n📅 Реєстрація: {data['reg']}"
        if data['photo']:
            await message.answer_photo(data['photo'], caption=text, parse_mode="Markdown")
        else:
            await message.answer(text, parse_mode="Markdown")
    else:
        await message.answer("❌ Гравця не знайдено.")
    await state.clear()

# --- ЛОГИКА БАНА ---
@dp.callback_query(F.data == "admin_ban")
async def ban_1(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return await callback.answer("❌ Немає прав", show_alert=True)
    await callback.message.answer("🔨 Введіть нік для бану:")
    await state.set_state(Form.ban_nick)
    await callback.answer()

@dp.message(Form.ban_nick)
async def ban_2(message: types.Message, state: FSMContext):
    await state.update_data(n=message.text.lower())
    await message.answer("⏰ Термін (днів) або 'перм':")
    await state.set_state(Form.ban_time)

@dp.message(Form.ban_time)
async def ban_3(message: types.Message, state: FSMContext):
    t_text = message.text.lower()
    if any(x in t_text for x in ["перм", "назавжди", "0"]):
        expiry = "permanent"
    else:
        nums = re.findall(r'\d+', t_text)
        expiry = (datetime.now() + timedelta(days=int(nums[0]))).isoformat() if nums else "permanent"
    
    await state.update_data(t=expiry)
    await message.answer("📄 Причина:")
    await state.set_state(Form.ban_reason)

@dp.message(Form.ban_reason)
async def ban_4(message: types.Message, state: FSMContext):
    d = await state.get_data()
    reason_text = message.text
    admin_name = message.from_user.username or str(message.from_user.id)
    
    try:
        conn = await asyncpg.connect(DB_URL)
        # Указываем колонки (nick, expiry, reason, admin) точно как в базе
        await conn.execute("""
            INSERT INTO bans (nick, expiry, reason, admin) 
            VALUES ($1, $2, $3, $4) 
            ON CONFLICT (nick) 
            DO UPDATE SET expiry=$2, reason=$3, admin=$4
        """, d['n'], d['t'], reason_text, admin_name)
        
        await conn.close()
        await message.answer(f"✅ Користувач {d['n']} забанений.", reply_markup=main_kb(message.from_user.id))
    except Exception as e:
        print(f"ОШИБКА БАЗЫ: {e}")
        await message.answer(f"❌ Ошибка при записи в базу: {e}")
        
    await state.clear()

# --- НОВАЯ ЛОГИКА РАЗБАНА (ИСПРАВЛЕНО) ---
@dp.callback_query(F.data == "admin_unban")
async def unban_1(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return await callback.answer("❌ Немає прав", show_alert=True)
    await callback.message.answer("🔓 Введіть нік для розбану:")
    await state.set_state(Form.unban_nick)
    await callback.answer()

@dp.message(Form.unban_nick)
async def unban_proc(message: types.Message, state: FSMContext):
    nick = message.text.lower()
    conn = await asyncpg.connect(DB_URL)
    
    # Сначала проверяем, есть ли вообще такой бан
    res = await conn.fetchrow("SELECT * FROM bans WHERE nick = $1", nick)
    
    if res:
        # Если бан найден — УДАЛЯЕМ его
        await conn.execute("DELETE FROM bans WHERE nick = $1", nick)
        await message.answer(f"✅ Гравець {nick} успішно розбанений!")
    else:
        # Если бана нет
        await message.answer(f"❓ Гравця {nick} немає в списку банів.")
    
    await conn.close()
    await state.clear()

# --- ПРОВЕРКА БАНА ---
@dp.callback_query(F.data == "btn_check_ban")
async def check_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введіть нік для перевірки:")
    await state.set_state(Form.check_nick)
    await callback.answer()

@dp.message(Form.check_nick)
async def check_proc(message: types.Message, state: FSMContext):
    nick = message.text.lower().strip()
    try:
        conn = await asyncpg.connect(DB_URL)
        res = await conn.fetchrow("SELECT * FROM bans WHERE nick=$1", nick)
        
        if res:
            # Получаем данные по именам колонок
            reason = res['reason']
            expiry = res['expiry']
            
            if expiry != "permanent":
                try:
                    expiry_dt = datetime.fromisoformat(expiry)
                    if datetime.now() > expiry_dt:
                        await conn.execute("DELETE FROM bans WHERE nick=$1", nick)
                        await conn.close()
                        return await message.answer(f"✅ Термін бану гравця {nick} минув. Його розбанено.")
                except Exception as e:
                    print(f"Ошибка даты: {e}")

            await message.answer(f"🚫 Гравець {nick} в бані.\nПричина: {reason}")
        else:
            await message.answer("✅ Бан не знайдено.")
        
        await conn.close()
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        await message.answer("❌ Помилка при зверненні до бази даних.")
    
    await state.clear()

# --- СКАРГИ ---
# --- ВХОД В ФОРМЫ ---
@dp.callback_query(F.data.in_(["btn_complaint", "btn_appeal"]))
async def start_player_form(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "btn_complaint":
        await callback.message.answer("📝 Скарга на гравця\n1. Введіть нік порушника:")
        await state.set_state(Form.comp_target_nick)
    else:
        await callback.message.answer("⚖️ Апеляція\n1. Де було видано покарання? (Роблокс або Телеграм):")
        await state.set_state(Form.app_place)
    await callback.answer()

# --- ЦЕПОЧКА СКАРГИ ---
@dp.message(Form.comp_user_nick)
async def comp_final(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_nick = message.text # Ник заявителя из последнего сообщения
    
    caption = (
        f"📩 НОВА СКАРГА\n"
        f"👤 Від: {message.from_user.mention_html()}\n\n"
        f"1️⃣ Нік порушника: {user_data['target_nick']}\n"
        f"2️⃣ Порушення: {user_data['violation']}\n"
        f"3️⃣ Докази: {user_data['proofs_text']}\n"
        f"4️⃣ Нік заявника: {user_nick}"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="✅ Прийняти", callback_data=f"adm_ok_{message.from_user.id}"))
    kb.row(types.InlineKeyboardButton(text="❌ Відхилити", callback_data=f"adm_no_{message.from_user.id}"))
    
    # Логика отправки в зависимости от типа доказательств
    p_type = user_data.get("proofs_type")
    file_id = user_data.get("proofs_file")

    try:
        if p_type == "photo":
            await bot.send_photo(GROUP_ID, photo=file_id, caption=caption, 
                                 message_thread_id=THREAD_ID, reply_markup=kb.as_markup(), parse_mode="HTML")
        elif p_type == "video":
            await bot.send_video(GROUP_ID, video=file_id, caption=caption, 
                                 message_thread_id=THREAD_ID, reply_markup=kb.as_markup(), parse_mode="HTML")
        else:
            await bot.send_message(GROUP_ID, caption, 
                                   message_thread_id=THREAD_ID, reply_markup=kb.as_markup(), parse_mode="HTML")
        
        await message.answer("✅ Вашу скаргу з медіа-доказами надіслано!")
    except Exception as e:
        await message.answer("❌ Помилка при відправці скарги. Спробуйте ще раз.")
        print(f"Ошибка отправки: {e}")

    await state.clear()

# --- ЦЕПОЧКА АПЕЛЛЯЦІЇ ---
@dp.message(Form.app_place)
async def app_1(message: types.Message, state: FSMContext):
    await state.update_data(place=message.text)
    await message.answer("2. Ваш нік (якщо ТГ — поставте '-'):")
    await state.set_state(Form.app_user_nick)

@dp.message(Form.app_user_nick)
async def app_2(message: types.Message, state: FSMContext):
    await state.update_data(nick=message.text)
    await message.answer("3. За що вам було видано покарання?")
    await state.set_state(Form.app_reason)

@dp.message(Form.app_reason)
async def app_3(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer("4. Чому ми повинні вас розблокувати/розмутити?")
    await state.set_state(Form.app_why_unban)

@dp.message(Form.app_why_unban)
async def app_final(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    caption = (
        f"⚖️ НОВА АПЕЛЯЦІЯ\n"
        f"👤 Від: {message.from_user.mention_html()}\n\n"
        f"1️⃣ Місце: {user_data['place']}\n"
        f"2️⃣ Нік: {user_data['nick']}\n"
        f"3️⃣ Причина бана: {user_data['reason']}\n"
        f"4️⃣ Чому розбанити: {message.text}"
    )
    
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="✅ Прийняти", callback_data=f"adm_ok_{message.from_user.id}"))
    kb.row(types.InlineKeyboardButton(text="❌ Відхилити", callback_data=f"adm_no_{message.from_user.id}"))
    
    await bot.send_message(GROUP_ID, caption, message_thread_id=THREAD_ID, reply_markup=kb.as_markup(), parse_mode="HTML")
    await message.answer("✅ Вашу апеляцію надіслано адміністрації!")
    await state.clear()

# --- ВЕРДИКТ АДМИНА (ИСПРАВЛЕН ФИЛЬТР) ---
@dp.callback_query(F.data.startswith("adm_ok_") | F.data.startswith("adm_no_"))
async def adm_decision(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS: return
    action = "ПРИЙНЯТА" if "ok" in callback.data else "ВІДХИЛЕНА"
    uid = callback.data.split("_")[-1]
    await state.update_data(target=uid, status=action)
    await callback.message.answer(f"Рішення: {action}. Напишіть фідбек:")
    await state.set_state(Form.admin_feedback)
    await callback.answer()

@dp.message(Form.admin_feedback)
async def adm_feedback_send(message: types.Message, state: FSMContext):
    d = await state.get_data()
    try:
        await bot.send_message(d['target'], f"🔔 Результат: {d['status']}\nКоментар: {message.text}")
        await message.answer("✅ Відправлено.")
    except:
        await message.answer("❌ Не надіслано (можливо, юзер заблокував бота).")
    await state.clear()

# --- СКАРГА НА АДМІНА ---
# --- ЦЕПОЧКА СКАРГИ НА АДМІНІСТРАТОРА ---

@dp.callback_query(F.data == "btn_adm_complaint")
async def adm_comp_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("👨‍✈️ Скарга на адміністратора\n1. Введіть нік або ID адміністратора:")
    await state.set_state(Form.adm_comp_target)
    await callback.answer()

@dp.message(Form.adm_comp_target)
async def adm_comp_1(message: types.Message, state: FSMContext):
    await state.update_data(adm_nick=message.text)
    await message.answer("2. Опишіть ситуацію (що саме порушив адмін?):")
    await state.set_state(Form.adm_comp_text)

@dp.message(Form.adm_comp_text)
async def adm_comp_2(message: types.Message, state: FSMContext):
    await state.update_data(adm_reason=message.text)
    await message.answer("3. Надішліть докази (фото, відео або посилання):")
    await state.set_state(Form.adm_comp_proofs)

@dp.message(Form.adm_comp_proofs)
async def adm_comp_final(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Формируем текст сообщения
    report_header = f"🚨 СКАРГА НА АДМІНІСТРАТОРА\n"
    report_body = (
        f"👤 Від кого: {message.from_user.mention_html()} (ID: `{message.from_user.id}`)\n"
        f"👤 На кого: {data['adm_nick']}\n"
        f"📝 Суть: {data['adm_reason']}\n"
    )
    
    # Собираем медиа
    photo = message.photo[-1].file_id if message.photo else None
    video = message.video.file_id if message.video else None
    text_proof = message.text if not (photo or video) else "Докази у вкладенні"
    
    full_caption = f"{report_header}\n{report_body}🖼 Докази: {text_proof}"

    # Рассылка всем Главным Админам
    for admin_id in CHIEF_ADMINS:
        try:
            if photo:
                await bot.send_photo(admin_id, photo=photo, caption=full_caption, parse_mode="HTML")
            elif video:
                await bot.send_video(admin_id, video=video, caption=full_caption, parse_mode="HTML")
            else:
                await bot.send_message(admin_id, full_caption, parse_mode="HTML")
        except Exception as e:
            print(f"Не вдалося надіслати адміну {admin_id}: {e}")

    await message.answer("✅ Ваша скарга надіслана вищій адміністрації на розгляд.")
    await state.clear()
    
@dp.callback_query(F.data == "btn_guide")
async def show_guide(callback: types.CallbackQuery):
    guide_text = (
        "📖 Посібник з використання бота\n\n"
        "🔹 🔍 Пошук RB: Введіть нік гравця, щоб отримати його ID, дату реєстрації та аватар.\n\n"
        "🔹 🚫 Перевірити бан: Дізнайтеся, чи занесений гравець до нашої бази банів та за що.\n\n"
        "🔹 📝 Скарга на гравця: Якщо ви помітили порушника, заповніть анкету. "
        "Бот попросить нік, опис порушення та фото/відео докази. Ваша заявка потрапить до модераторів.\n\n"
        "🔹 ⚖️ Апеляція: Якщо ви отримали бан і вважаєте його помилковим, заповніть цю форму.\n\n"
        "🔹 👨‍✈️ Скарга на адміна: Скарги на роботу персоналу йдуть напряму Вищій Адміністрації.\n\n"
        "⚠️ Порада: При надсиланні фото або відео, намагайтеся додавати опис до файлу одним повідомленням."
    )
    
    # Кнопка "Назад", чтобы вернуться в меню
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="to_main"))
    
    await callback.message.edit_text(guide_text, reply_markup=kb.as_markup(), parse_mode="Markdown")
    await callback.answer()

# Обработчик для возврата в главное меню
@dp.callback_query(F.data == "to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    await callback.message.edit_text(f"👋 Вітаємо!\nВаш ID: `{uid}`", 
                                 reply_markup=main_kb(uid), 
                                     parse_mode="Markdown")
async def handle(request):
    return web.Response(text="Bot is running")

async def start_webserver():    
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # КРИТИЧНО: Render автоматически назначает порт через переменную PORT
    port = int(os.environ.get("PORT", 10000)) 
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

async def main():
    await start_webserver()
    
    try:
        conn = await asyncpg.connect(DB_URL)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                nick TEXT PRIMARY KEY,
                expiry TEXT,
                reason TEXT,
                admin TEXT
            )
        ''')
        await conn.close()
        print("База данных подключена успешно!")
    except Exception as e:
        print(f"ОШИБКА БАЗЫ ДАННЫХ: {e}")
        # Не выходим из приложения, даем веб-серверу работать, 
        # чтобы Render не убил процесс сразу
    
    print("Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
