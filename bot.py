import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
# ======= SOZLAMALAR (SETTINGS) =======
BOT_TOKEN = "8411534123:AAEoPekkapXGDg6IxV3VsGtv_o0EML4yLPw" # @BotFather dan olingan token
ADMIN_IDS = [8023335798, 8066401832] # Adminlarning Telegram ID larini shu yerga yozing
LOG_CHANNEL_ID = -1003782480352 # Yangi foydalanuvchilar haqida xabar boradigan kanal ID si

# ======= MA'LUMOTLAR BAZASI (DATABASE) =======
import aiosqlite

DB_NAME = "stars_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                stars REAL DEFAULT 0,
                referrer_id INTEGER DEFAULT NULL,
                joined_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                channel_url TEXT
            )
        ''')
        try:
            await db.execute("ALTER TABLE users ADD COLUMN reward_given INTEGER DEFAULT 0")
        except:
            pass
        await db.commit()

async def check_and_reward_referrer(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT referrer_id, reward_given FROM users WHERE user_id = ?", (user_id,))
        user_data = await cursor.fetchone()
        
        if user_data and user_data[0] is not None and user_data[1] == 0:
            referrer_id = user_data[0]
            # Referalga stars qo'shish
            await db.execute("UPDATE users SET reward_given = 1 WHERE user_id = ?", (user_id,))
            await db.execute("UPDATE users SET stars = stars + 1.5 WHERE user_id = ?", (referrer_id,))
            await db.commit()
            return referrer_id
        return None

async def add_user(user_id, username, referrer_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)",
                (user_id, username, referrer_id)
            )
            await db.commit()
            return True
        return False

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def add_stars(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET stars = stars + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def get_top_users(limit=10):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id, username, stars FROM users ORDER BY stars DESC LIMIT ?", (limit,))
        return await cursor.fetchall()

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT channel_id, channel_url FROM channels")
        return await cursor.fetchall()

async def add_channel(channel_id, url):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO channels (channel_id, channel_url) VALUES (?, ?)", (channel_id, url))
        await db.commit()

async def remove_channel(channel_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        count = await cursor.fetchone()
        return count[0] if count else 0

# ======= KEYBOARDLAR (TUGMALAR) =======
def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Balans", callback_data="cabinet"),
             InlineKeyboardButton(text="📥 Stars ishlash", callback_data="referral")],
            [InlineKeyboardButton(text="💸 Stars Olish", callback_data="withdraw_menu"),
            InlineKeyboardButton(text="🏆 Reyting", callback_data="rating")],
            [InlineKeyboardButton(text="🎁 Premium Yutuqli O'yin", callback_data="premium_info")],
            [InlineKeyboardButton(text="📚 Qoidalar", callback_data="rules")]
        ]
    )

def referral_menu(ref_link: str):
    share_text = "Zo%27r%20bot%20ekan%21%20Kirib%20ko%27ring%20va%20Stars%20yig%27ing%21"
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↗️ Do'stlarga ulashish", url=share_url)],
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="back_to_main")]
        ]
    )

def back_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="back_to_main")]
        ]
    )

def withdraw_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧸,💝 15", callback_data="withdraw_15"),
                InlineKeyboardButton(text="🎁,🌹 25", callback_data="withdraw_25")],
            [InlineKeyboardButton(text="💐,🎂 50", callback_data="withdraw_50"),
            InlineKeyboardButton(text="💎 100", callback_data="withdraw_100")],
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="back_to_main")]
        ]
    )

def confirm_withdraw_menu(amount: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, olaman", callback_data=f"confirm_withdraw_{amount}"),
                InlineKeyboardButton(text="❌ Yo'q, bekor qilish", callback_data="withdraw_menu")
            ]
        ]
    )

def check_sub_menu(channels):
    buttons = []
    for i, ch in enumerate(channels, 1):
        buttons.append([InlineKeyboardButton(text=f"📢 Kanal {i} ga obuna bo'lish", url=ch[1])])
    
    buttons.append([InlineKeyboardButton(text="✅ Obunani tasdiqlash", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
             InlineKeyboardButton(text="✉️ Xabar yuborish (Tarqatish)", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel"),
             InlineKeyboardButton(text="➖ Kanalni o'chirish", callback_data="admin_remove_channel")],
            [InlineKeyboardButton(text="⭐️ Stars qo'shish", callback_data="admin_add_stars"),
             InlineKeyboardButton(text="📉 Stars ayirish", callback_data="admin_sub_stars")]
        ]
    )


# ======= BOT LOGIKASI =======
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class AdminStates(StatesGroup):
    broadcast = State()
    add_channel_id = State()
    add_channel_url = State()
    add_stars_user_id = State()
    add_stars_amount = State()
    sub_stars_user_id = State()
    sub_stars_amount = State()

async def is_subscribed(user_id: int):
    channels = await get_channels()
    if not channels:
        return True, channels
    
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False, channels
        except TelegramBadRequest:
            # Bot admin emas yoki kanal xato kiritilgan bo'lsa
            pass
        except Exception as e:
            logging.error(f"Xato: {e}")
            pass
    return True, channels


@dp.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split(" ")
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id == message.from_user.id:
            referrer_id = None
            
    is_new = await add_user(message.from_user.id, message.from_user.username or message.from_user.first_name, referrer_id)
    
    if is_new:
        user_link = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>"
        username_str = f" (@{message.from_user.username})" if message.from_user.username else ""
        try:
            await bot.send_message(
                LOG_CHANNEL_ID,
                f"🆕 <b>Yangi foydalanuvchi!</b>\n\n👤 {user_link}{username_str}\n🆔 ID: <code>{message.from_user.id}</code>"
            )
        except Exception as e:
            logging.error(f"Kanalga yuborishda xatolik: {e}")
            try:
                # Agar HTML parsering ishlamasa matn jo'natib ko'rish
                await bot.send_message(LOG_CHANNEL_ID, f"Yangi foydalanuvchi: {message.from_user.first_name} | ID: {message.from_user.id}")
            except:
                pass
    
    # Check subscription
    subbed, channels = await is_subscribed(message.from_user.id)
    
    if not subbed:
        await message.answer(
            "🛑 <b>Botdan to'liq foydalanish uchun quyidagi homiy kanallarga obuna bo'lishingiz shart!</b>\n\n"
            "Pastdagi havolalar orqali kanallarga qo'shiling va <b>\"✅ Obunani tasdiqlash\"</b> tugmasini bosing.",
            reply_markup=check_sub_menu(channels)
        )
        return

    rewarded_referrer_id = await check_and_reward_referrer(message.from_user.id)
    if rewarded_referrer_id:
        try:
            await bot.send_message(
                rewarded_referrer_id, 
                f"🎉 <b>Tabriklaymiz!</b> Sizning havolangiz orqali do'stingiz botga ulandi va sizga <b>1.5 stars</b> ⭐️ taqdim etildi!"
            )
        except:
            pass

    await message.answer(
        "👋 <b>Assalomu alaykum! Stars Botiga xush kelibsiz!</b>\n\n"
        "⭐️ Do'stlaringizni taklif qiling va har bir do'stingiz uchun qimmatbaho <b>1.5 Stars</b> ga ega bo'ling!\n"
        "🎁 Shuningdek har oy juma kuni eng ko'p yulduz yig'ganlar uchun <b>Telegram Premium</b> yutuqli o'yinlari o'tkaziladi!\n\n"
        "👇 Asosiy menyudan o'zingizga kerakli bo'limni tanlang:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(call: CallbackQuery):
    subbed, channels = await is_subscribed(call.from_user.id)
    if subbed:
        await call.message.delete()
        
        rewarded_referrer_id = await check_and_reward_referrer(call.from_user.id)
        if rewarded_referrer_id:
            try:
                await bot.send_message(
                    rewarded_referrer_id, 
                    f"🎉 <b>Tabriklaymiz!</b> Sizning havolangiz orqali do'stingiz botga ulandi va sizga <b>1.5 stars</b> ⭐️ taqdim etildi!"
                )
            except:
                pass
        await call.message.answer(
            "✅ <b>Obunalar tasdiqlandi!</b>\n\n"
            "👋 <b>Assalomu alaykum! Stars Botiga xush kelibsiz!</b>\n\n"
            "⭐️ Do'stlaringizni taklif qiling va har bir do'stingiz uchun qimmatbaho <b>1.5 Stars</b> ga ega bo'ling!\n"
            "🎁 Shuningdek har oy juma kuni eng ko'p yulduz yig'ganlar uchun <b>Telegram Premium</b> yutuqli o'yinlari o'tkaziladi!\n\n"
            "👇 Asosiy menyudan o'zingizga kerakli bo'limni tanlang:", 
            reply_markup=main_menu()
        )
    else:
        await call.answer("❌ Kechirasiz, siz hali barcha kanallarga obuna bo'lmagansiz!", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def cb_back_to_main(call: CallbackQuery):
    await call.message.edit_text(
        "👋 <b>Assalomu alaykum! Stars Botiga xush kelibsiz!</b>\n\n"
        "⭐️ Do'stlaringizni taklif qiling va har bir do'stingiz uchun qimmatbaho <b>1.5 Stars</b> ga ega bo'ling!\n"
        "🎁 Shuningdek har oy juma kuni eng ko'p yulduz yig'ganlar uchun <b>Telegram Premium</b> yutuqli o'yinlari o'tkaziladi!\n\n"
        "👇 Asosiy menyudan o'zingizga kerakli bo'limni tanlang:",
        reply_markup=main_menu()
    )
    await call.answer()
    
from datetime import datetime

@dp.callback_query(F.data == "withdraw_menu")
async def cb_withdraw_menu(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    stars = user[2] if user else 0
    await call.message.edit_text(
        f"💸 <b>Stars yechib olish bo'limi!</b>\n\n"
        f"Sizning balansingiz: <b>{stars} Stars</b> ⭐️\n\n"
        f"Qancha stars yechib olmoqchisiz? Quyidagi tugmalardan birini tanlang:",
        reply_markup=withdraw_keyboard()
    )
    await call.answer()

@dp.callback_query(F.data.startswith("withdraw_"))
async def cb_withdraw_amount(call: CallbackQuery):
    if call.data == "withdraw_menu":
        return
    amount_str = call.data.split("_")[1]
    if not amount_str.isdigit():
        return
        
    amount = int(amount_str)
    user = await get_user(call.from_user.id)
    stars = user[2] if user else 0
    
    if stars < amount:
        await call.answer(f"❌ Kechirasiz, hisobingizda {amount} Stars mavjud emas! Sizda {stars} Stars bor.", show_alert=True)
        return
        
    await call.message.edit_text(
        f"❓ Siz haqiqatan ham <b>{amount} Stars</b> yechib olmoqchimisiz?\n\n"
        f"Balansingizdan aynan shu miqdor yechib olinadi va ko'rib chiqishga yuboriladi.",
        reply_markup=confirm_withdraw_menu(amount)
    )
    await call.answer()

@dp.callback_query(F.data.startswith("confirm_withdraw_"))
async def cb_confirm_withdraw(call: CallbackQuery):
    amount = int(call.data.split("_")[2])
    user = await get_user(call.from_user.id)
    stars = user[2] if user else 0
    
    if stars < amount:
        await call.message.edit_text("❌ Xatolik yuz berdi yoki balansingiz yetarli emas.", reply_markup=back_menu())
        await call.answer()
        return

    # User dan pulni ayirib tashlash (manfiy qo'shish)
    await add_stars(call.from_user.id, -amount)
    
    # Adminga va kanalga yuboriladigan xabar
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_link = f"<a href='tg://user?id={call.from_user.id}'>{call.from_user.first_name}</a>"
    username_str = f" (@{call.from_user.username})" if call.from_user.username else ""
    
    log_text = (
        f"💸 <b>Yangi to'lov so'rovi!</b>\n\n"
        f"👤 Foydalanuvchi: {user_link}{username_str}\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"⭐️ Miqdor: <b>{amount} Stars</b>\n"
        f"📅 Sana: {now}"
    )

    # Adminlarga yuborish
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, log_text)
        except:
            pass
            
    # Kanalga yuborish
    try:
        await bot.send_message(LOG_CHANNEL_ID, log_text)
    except:
        pass

    await call.message.edit_text(
        f"✅ <b>So'rovingiz qabul qilindi!</b>\n\n"
        f"Miqdor: {amount} Stars tez orada administrator tomonidan ko'rib chiqiladi va to'lab beriladi.",
        reply_markup=back_menu()
    )
    await call.answer("✅ Muvaffaqiyatli!", show_alert=True)

@dp.callback_query(F.data == "referral")
async def cb_referral(call: CallbackQuery):
    bot_me = await bot.get_me()
    ref_link = f"https://t.me/{bot_me.username}?start={call.from_user.id}"
    await call.message.edit_text(
        f"🔗 <b>Sizning shaxsiy referal havolangiz:</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"🚀 Ushbu havolani do'stlaringizga yuboring va har bir botga kirgan do'stingiz uchun <b>1.5 Stars</b> ⭐️ yig'ing.",
        reply_markup=referral_menu(ref_link)
    )
    await call.answer()

@dp.callback_query(F.data == "cabinet")
async def cb_cabinet(call: CallbackQuery):
    user = await get_user(call.from_user.id)
    if user:
        stars = user[2]
        await call.message.edit_text(
            f"👤 <b>Shaxsiy Kabinetingiz:</b>\n\n"
            f"🆔 ID Rqamingiz: <code>{call.from_user.id}</code>\n"
            f"👤 Ismingiz: {user[1]}\n"
            f"⭐️ Yig'ilgan Yulduzlar: <b>{stars} Stars</b>",
            reply_markup=back_menu()
        )
    await call.answer()

@dp.callback_query(F.data == "rating")
async def cb_rating(call: CallbackQuery):
    top_users = await get_top_users(10)
    text = "🏆 <b>TOP 10 - Eng ko'p yulduzcha yig'gan peshqadamlar:</b>\n\n"
    if not top_users:
        text += "<i>Hali hech kim yulduzcha yig'madi.</i>"
    else:
        for i, u in enumerate(top_users, 1):
            name = u[1] if u[1] else "Foydalanuvchi"
            text += f"<b>{i}.</b> {name} — <b>{u[2]}</b> ⭐️\n"
    await call.message.edit_text(text, reply_markup=back_menu())
    await call.answer()

@dp.callback_query(F.data == "rules")
async def cb_rules(call: CallbackQuery):
    await call.message.edit_text(
        "📚 <b>Bot qoidalari:</b>\n\n"
        "1. Majburiy kanallardan chiqib ketish taqiqlanadi.\n"
        "2. Soxta (fake) akkauntlar orqali referal yig'ish qat'iyan man etiladi.\n"
        "3. Yutuqlar faqat haqqoniy to'plaganlarga taqdim etiladi.\n\n"
        "🛑 Qoidalarni buzganlar ogohlantirishsiz botdan bloklanadi. Vijdoningizga bogliq, Halol ishlang!",
        reply_markup=back_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "user_stats")
async def cb_user_stats(call: CallbackQuery):
    stats = await get_stats()
    await call.message.edit_text(
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Botning jami a'zolari: <b>{stats}</b> ta\n\n"
        f"<i>Siz ham o'z hissangizni qo'shing va ko'proq do'stlaringizni taklif qiling!</i>",
        reply_markup=back_menu()
    )
    await call.answer()

@dp.callback_query(F.data == "premium_info")
async def cb_premium_info(call: CallbackQuery):
    await call.message.edit_text(
        "🎁 <b>TELEGRAM PREMIUM YUTUQLI O'YINI</b>\n\n"
        "📅 O'yin har oy juma kuni bo'lib o'tadi.\n"
        "🔝 Eng ko'p <b>Stars</b> to'plaganlar orasida random orqali <b>Telegram Premium</b> g'olibi aniqlanadi!\n\n"
        "<i>💡 Maslahat: Ko'proq do'stingizni chaqirsangiz (ko'p stars yiqqan bo'lsangiz), yutish imkoniyatingiz shuncha yuqori bo'ladi!</i>",
        reply_markup=back_menu()
    )
    await call.answer()

# ======= ADMIN PANEL ========
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("👑 <b>Admin panelga xush kelibsiz, Xo'jayin!</b>\n\nQuyidan amalni tanlang:", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(call: CallbackQuery):
    if call.from_user.id in ADMIN_IDS:
        stats = await get_stats()
        await call.message.edit_text(f"📊 <b>Bot Statistikasi</b>\n\n👥 Jami foydalanuvchilar: <b>{stats}</b> ta", reply_markup=admin_menu())
    await call.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id in ADMIN_IDS:
        await call.message.answer("✉️ <b>Tarqatish uchun xabarni yuboring:</b>\n<i>(Matn, Rasm, Video yoki boshqa format bo'lishi mumkin)</i>")
        await state.set_state(AdminStates.broadcast)
    await call.answer()

@dp.message(AdminStates.broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    users = await get_all_users()
    count = 0
    msg = await message.answer("⏳ <i>Xabar tarqatish boshlandi... Iltimos kuting.</i>")
    for uid in users:
        try:
            await message.send_copy(chat_id=uid)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await msg.edit_text(f"✅ Xabar <b>{count}</b> ta foydalanuvchiga muvaffaqiyatli yetib bordi!", reply_markup=admin_menu())
    await state.clear()


@dp.callback_query(F.data == "admin_add_channel")
async def cb_admin_add_channel(call: CallbackQuery, state: FSMContext):
    if call.from_user.id in ADMIN_IDS:
        await call.message.answer(
            "➕ <b>Yangi kanal qo'shish</b>\n\n"
            "Iltimos, avvalo kanal qidiruv ID sini (masalan: <b>-100123456789</b>) yoki @kanal_username shaklida yuboring:\n\n"
            "<i>⚠️ Eslatma: Bot o'sha kanalda ADMIN bo'lishi shart! Agar u kanal bo'lsa ID -100 dan boshlanishi kerak (Supergroup/Channel).</i>"
        )
        await state.set_state(AdminStates.add_channel_id)
    await call.answer()

@dp.message(AdminStates.add_channel_id)
async def process_add_channel_id(message: Message, state: FSMContext):
    chan_id = message.text
    if chan_id.startswith('@'):
        pass
    else:
        try:
            chan_id = int(chan_id)
        except ValueError:
            await message.answer("❌ ID noto'g'ri kiritildi. Qayta urinib ko'ring yoki /admin orqali bekor qiling.")
            return

    await state.update_data(channel_id=chan_id)
    await message.answer("Endi ushbu kanalga havola (URL) yuboring (Masalan: https://t.me/kanal_nomi):")
    await state.set_state(AdminStates.add_channel_url)

@dp.message(AdminStates.add_channel_url)
async def process_add_channel_url(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data['channel_id']
    channel_url = message.text
    
    await add_channel(channel_id, channel_url)
    await message.answer(f"✅ Kanal ajoyib tarzda tizimga qo'shildi!", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_remove_channel")
async def cb_admin_remove_channel(call: CallbackQuery):
    if call.from_user.id in ADMIN_IDS:
        channels = await get_channels()
        if not channels:
            await call.message.edit_text("❌ Tizimda majburiy obuna kanallari mavjud emas.", reply_markup=admin_menu())
            return

        buttons = []
        for ch in channels:
            buttons.append([InlineKeyboardButton(text=f"🗑 O'chirish: {ch[0]}", callback_data=f"del_ch_{ch[0]}")])
        buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back")])
        
        rm = InlineKeyboardMarkup(inline_keyboard=buttons)
        await call.message.edit_text("O'chirish uchun kerakli kanalni tanlang:", reply_markup=rm)
    await call.answer()

@dp.callback_query(F.data.startswith("del_ch_"))
async def cb_del_ch(call: CallbackQuery):
    if call.from_user.id in ADMIN_IDS:
        ch_id = call.data.replace("del_ch_", "")
        try:
            ch_id = int(ch_id)
        except ValueError:
            pass
            
        await remove_channel(ch_id)
        await call.answer("✅ Kanal o'chirildi!", show_alert=True)
        # return to admin menu
        await cb_admin_remove_channel(call)
    await call.answer()

@dp.callback_query(F.data == "admin_back")
async def cb_admin_back(call: CallbackQuery):
    if call.from_user.id in ADMIN_IDS:
        await call.message.edit_text("👑 <b>Admin panelga xush kelibsiz, Xo'jayin!</b>\n\nQuyidan amalni tanlang:", reply_markup=admin_menu())
    await call.answer()

@dp.callback_query(F.data == "admin_add_stars")
async def cb_admin_add_stars(call: CallbackQuery, state: FSMContext):
    if call.from_user.id in ADMIN_IDS:
        await call.message.edit_text("⭐️ <b>Stars qo'shish</b>\n\nFoydalanuvchi ID raqamini kiriting:")
        await state.set_state(AdminStates.add_stars_user_id)
    await call.answer()

@dp.message(AdminStates.add_stars_user_id)
async def process_add_stars_user_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID noto'g'ri kiritildi. Raqam kiriting yeki /admin kiritib bekor qiling.")
        return
    
    user = await get_user(user_id)
    if not user:
        await message.answer("❌ Bunday foydalanuvchi topilmadi. Boshqa ID kiriting yeki /admin kiritib bekor qiling:")
        return

    await state.update_data(target_user_id=user_id)
    await message.answer(f"Foydalanuvchi: <b>{user[1]}</b>\nJoriy balansi: <b>{user[2]} Stars</b>\n\nQancha stars qo'shmoqchisiz? (faqat raqam bilan yozing):")
    await state.set_state(AdminStates.add_stars_amount)

@dp.message(AdminStates.add_stars_amount)
async def process_add_stars_amount(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("❌ Miqdor noto'g'ri kiritildi. Faqat raqam kiriting:")
        return
        
    data = await state.get_data()
    target_user_id = data['target_user_id']
    
    await add_stars(target_user_id, amount)
    
    await message.answer(f"✅ Foydalanuvchi (ID: {target_user_id}) hisobiga <b>{amount} Stars</b> muvaffaqiyatli qo'shildi!", reply_markup=admin_menu())
    
    try:
        await bot.send_message(target_user_id, f"🎉 <b>Tabriklaymiz!</b> Administrator tomonidan hisobingizga <b>{amount} Stars</b> qo'shildi!")
    except:
        pass
        
    await state.clear()

@dp.callback_query(F.data == "admin_sub_stars")
async def cb_admin_sub_stars(call: CallbackQuery, state: FSMContext):
    if call.from_user.id in ADMIN_IDS:
        await call.message.edit_text("📉 <b>Stars ayirish</b>\n\nFoydalanuvchi ID raqamini kiriting:")
        await state.set_state(AdminStates.sub_stars_user_id)
    await call.answer()

@dp.message(AdminStates.sub_stars_user_id)
async def process_sub_stars_user_id(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID noto'g'ri kiritildi. Raqam kiriting yeki /admin kiritib bekor qiling.")
        return
    
    user = await get_user(user_id)
    if not user:
        await message.answer("❌ Bunday foydalanuvchi topilmadi. Boshqa ID kiriting yeki /admin kiritib bekor qiling:")
        return

    await state.update_data(target_user_id=user_id)
    await message.answer(f"Foydalanuvchi: <b>{user[1]}</b>\nJoriy balansi: <b>{user[2]} Stars</b>\n\nQancha stars ayirmoqchisiz? (faqat raqam bilan yozing):")
    await state.set_state(AdminStates.sub_stars_amount)

@dp.message(AdminStates.sub_stars_amount)
async def process_sub_stars_amount(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("❌ Miqdor noto'g'ri kiritildi. Faqat raqam kiriting:")
        return
        
    data = await state.get_data()
    target_user_id = data['target_user_id']
    
    await add_stars(target_user_id, -amount)
    
    await message.answer(f"✅ Foydalanuvchi (ID: {target_user_id}) hisobidan <b>{amount} Stars</b> muvaffaqiyatli ayirildi!", reply_markup=admin_menu())
    
    try:
        await bot.send_message(target_user_id, f"📉 Administrator tomonidan hisobingizdan <b>{amount} Stars</b> olib tashlandi.")
    except:
        pass
        
    await state.clear()

async def main():
    await init_db()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    
    print("Bot muvaffaqiyatli ishga tushdi!")
    
    # Run long polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti")

def run_web():
    port = 10000
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

threading.Thread(target=run_web).start()
