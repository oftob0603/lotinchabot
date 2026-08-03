"""
Kanal -> Izoh (comment) boti  (faqat admin(lar) uchun)
========================================================

Vazifasi:
  Kanalga post tashlanganda (matn / rasm / video / animatsiya / hujjat),
  agar kanal diskussiya (discussion) guruhiga bog'langan bo'lsa, Telegram
  o'sha postni avtomatik ravishda guruhga forward qiladi. Ushbu bot aynan
  shu avtomatik forward xabarni aniqlab, unga izoh (comment) sifatida
  KRILLCHA matn bilan (va bo'lsa rasm/video bilan birga) javob yozadi.

  Matnni krillchaga o'girishda @username va havolalar (link)lar
  O'ZGARTIRILMAYDI. @username'dan oldingi emoji(lar) bo'lsa olib
  tashlanadi.

XAVFSIZLIK (faqat egasi uchun ishlaydi):
  - Botga /start bosgan har qanday kishi emas, faqat ADMIN_IDS
    ro'yxatidagi foydalanuvchilar bilan ishlaydi.
  - Botni biror kanal yoki guruhga ADMIN_IDS'da bo'lmagan kishi
    qo'shsa, bot avtomatik o'sha chatdan CHIQIB KETADI.
  - Bot biror guruh/kanalda ishlashi uchun, ADMIN_IDS'dagi kishi
    botni o'sha yerga qo'shgach, O'ZI O'SHA CHATDA /add deb yozishi
    kerak — shundagina bot o'sha chatni "ruxsat berilgan" deb
    belgilaydi va izoh yozish funksiyasini boshlaydi. /add
    yozilmagan chatda bot hech narsa qilmaydi.
  - /removechat — joriy chatni ruxsat ro'yxatidan olib tashlaydi.
  - /listchats — ruxsat berilgan barcha chatlarni ko'rsatadi.
  - /chatid — joriy chat ID'si va holatini ko'rsatadi.
  - Mavjud adminlar /addadmin va /removeadmin buyruqlari orqali
    yangi adminlarni qo'sha/o'chira oladi (bu ro'yxat admins.json
    fayliga saqlanadi, .env dagi ADMIN_IDS esa boshlang'ich ro'yxat).
  - /myid buyrug'i orqali istalgan kishi o'z Telegram ID'sini bilib
    olishi mumkin (buni sizga yuborib, admin sifatida qo'shdirishi
    uchun kerak bo'ladi).
  - Admin bo'lmagan kishi botga /start bossa, "Kanalimizga e'lon berish
    uchun <CONTACT_USERNAME>ga yozing" degan xabar ko'rsatiladi
    (.env dagi CONTACT_USERNAME orqali sozlanadi).
  - Guruhda kimdir qo'shilganda/chiqqanda Telegram chiqaradigan
    "... guruhga qo'shildi" / "... guruhdan chiqdi" xabarlari
    ruxsat berilgan chatlarda avtomatik o'chiriladi (buning uchun
    botda "Delete Messages" admin huquqi yoqilgan bo'lishi shart).

O'rnatish:
  pip install -r requirements.txt

Sozlash (majburiy qadamlar):
  1. @BotFather orqali bot yarating, tokenini oling.
  2. Loyihadagi .env.example faylidan nusxa olib .env deb saqlang,
     ichiga BOT_TOKEN va ADMIN_IDS (o'z Telegram ID'ingiz) ni yozing.
     O'z ID'ingizni bilish uchun botga /myid deb yozing (avval
     ADMIN_IDS bo'sh bo'lsa ham ishlaydi, keyin ID'ni .env ga qo'shing).
  3. Botni KANALGA admin qilib qo'shing.
  4. Kanalingizga diskussiya guruhini ulang (agar ulanmagan bo'lsa:
     Kanal sozlamalari -> Discussion -> guruh tanlang).
  5. Botni O'SHA DISKUSSIYA GURUHIGA ham admin qilib qo'shing
     (xabar yozish huquqi bilan). MUHIM: buni albatta ADMIN_IDS
     ro'yxatidagi hisobingiz orqali qiling — aks holda bot
     avtomatik chiqib ketadi.

     ESLATMA: "Remain Anonymous" / "Anonim" admin huquqini yoqib
     qo'ysangiz ham, bu faqat ODAM uchun ishlaydi — Bot API orqali
     ishlaydigan botlar baribir bot nomidan yozadi.
  6. python channel_comment_bot.py
"""

import asyncio
import json
import logging
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    ChatMemberUpdated,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Sozlamalar (.env fayldan o'qiladi)
# ---------------------------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN topilmadi. .env faylga BOT_TOKEN=... deb yozing.")

ADMINS_FILE = os.getenv("ADMINS_FILE", "admins.json")
ALLOWED_CHATS_FILE = os.getenv("ALLOWED_CHATS_FILE", "allowed_chats.json")

# Admin bo'lmagan kishi botga /start bosganda ko'rsatiladigan kontakt
# (e'lon berish uchun murojaat qilinadigan admin username'i)
CONTACT_USERNAME = os.getenv("CONTACT_USERNAME", "@admin")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096
MEDIA_GROUP_DELAY = 1.5  # sekund

pending_groups: dict[str, list[Message]] = {}
pending_tasks: dict[str, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Admin ro'yxati va ruxsat berilgan chatlar (fayllarda saqlanadi)
# ---------------------------------------------------------------------------

def _load_env_admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "")
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _load_json_set(path: str) -> set[int]:
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(int(x) for x in json.load(f))
    except Exception:
        logging.exception("Faylni o'qib bo'lmadi: %s", path)
        return set()


def _save_json_set(path: str, values: set[int]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(values), f)
    except Exception:
        logging.exception("Faylga yozib bo'lmadi: %s", path)


admin_ids: set[int] = _load_env_admin_ids() | _load_json_set(ADMINS_FILE)
allowed_chats: set[int] = _load_json_set(ALLOWED_CHATS_FILE)


def save_admins() -> None:
    # .env dagilarni faylga yozmaymiz, faqat runtime'da qo'shilganlarni
    _save_json_set(ADMINS_FILE, admin_ids)


def save_allowed_chats() -> None:
    _save_json_set(ALLOWED_CHATS_FILE, allowed_chats)


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in admin_ids


# ---------------------------------------------------------------------------
# Lotin -> Kirill transliteratsiya (o'zbekcha)
# ---------------------------------------------------------------------------

MULTI_CHAR = [
    ("o'", "ў"), ("oʻ", "ў"), ("o‘", "ў"), ("o’", "ў"),
    ("O'", "Ў"), ("Oʻ", "Ў"), ("O‘", "Ў"), ("O’", "Ў"),
    ("g'", "ғ"), ("gʻ", "ғ"), ("g‘", "ғ"), ("g’", "ғ"),
    ("G'", "Ғ"), ("Gʻ", "Ғ"), ("G‘", "Ғ"), ("G’", "Ғ"),
    ("sh", "ш"), ("Sh", "Ш"), ("SH", "Ш"),
    ("ch", "ч"), ("Ch", "Ч"), ("CH", "Ч"),
    ("yo", "ё"), ("Yo", "Ё"), ("YO", "Ё"),
    ("yu", "ю"), ("Yu", "Ю"), ("YU", "Ю"),
    ("ya", "я"), ("Ya", "Я"), ("YA", "Я"),
    ("ye", "е"), ("Ye", "Е"), ("YE", "Е"),
    ("ng", "нг"), ("Ng", "Нг"), ("NG", "НГ"),
]

SINGLE_CHAR = {
    "a": "а", "A": "А", "b": "б", "B": "Б", "d": "д", "D": "Д",
    "e": "е", "E": "Е", "f": "ф", "F": "Ф", "g": "г", "G": "Г",
    "h": "ҳ", "H": "Ҳ", "i": "и", "I": "И", "j": "ж", "J": "Ж",
    "k": "к", "K": "К", "l": "л", "L": "Л", "m": "м", "M": "М",
    "n": "н", "N": "Н", "o": "о", "O": "О", "p": "п", "P": "П",
    "q": "қ", "Q": "Қ", "r": "р", "R": "Р", "s": "с", "S": "С",
    "t": "т", "T": "Т", "u": "у", "U": "У", "v": "в", "V": "В",
    "x": "х", "X": "Х", "y": "й", "Y": "Й", "z": "з", "Z": "З",
    "c": "ц", "C": "Ц",
}

PROTECTED_RE = re.compile(r'(@\w+|https?://\S+|t\.me/\S+|www\.\S+)')

EMOJI_RANGES = (
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "\U0000200D"
)

EMOJI_BEFORE_MENTION_RE = re.compile(rf"(?:[{EMOJI_RANGES}]+\s*)+(?=@\w+)")


def _transliterate_plain(text: str) -> str:
    for lat, cyr in MULTI_CHAR:
        text = text.replace(lat, cyr)
    return "".join(SINGLE_CHAR.get(ch, ch) for ch in text)


def lotin_to_kirill(text: str) -> str:
    """Matnni krillchaga o'giradi, @username va linklarni o'zgartirmaydi.
    @username'dan oldingi emoji(lar) bo'lsa, ular olib tashlanadi."""
    if not text:
        return text
    text = EMOJI_BEFORE_MENTION_RE.sub("", text)
    parts = PROTECTED_RE.split(text)
    out = []
    for part in parts:
        if PROTECTED_RE.fullmatch(part or ""):
            out.append(part)
        else:
            out.append(_transliterate_plain(part))
    return "".join(out)


# ---------------------------------------------------------------------------
# Kirill -> Lotin (teskari) transliteratsiya
# ---------------------------------------------------------------------------

# Bitta kirillcha harf ba'zan 2 ta lotincha harfga mos keladi (ш->sh va h.k.)
CYR_TO_LAT = {
    "а": "a", "А": "A", "б": "b", "Б": "B", "д": "d", "Д": "D",
    "е": "e", "Е": "E", "ф": "f", "Ф": "F", "г": "g", "Г": "G",
    "ҳ": "h", "Ҳ": "H", "и": "i", "И": "I", "ж": "j", "Ж": "J",
    "к": "k", "К": "K", "л": "l", "Л": "L", "м": "m", "М": "M",
    "н": "n", "Н": "N", "о": "o", "О": "O", "п": "p", "П": "P",
    "қ": "q", "Қ": "Q", "р": "r", "Р": "R", "с": "s", "С": "S",
    "т": "t", "Т": "T", "у": "u", "У": "U", "в": "v", "В": "V",
    "х": "x", "Х": "X", "й": "y", "Й": "Y", "з": "z", "З": "Z",
    "ц": "c", "Ц": "C",
    "ш": "sh", "Ш": "Sh",
    "ч": "ch", "Ч": "Ch",
    "ё": "yo", "Ё": "Yo",
    "ю": "yu", "Ю": "Yu",
    "я": "ya", "Я": "Ya",
    "ў": "o'", "Ў": "O'",
    "ғ": "g'", "Ғ": "G'",
    "ъ": "'", "Ъ": "'",
    "э": "e", "Э": "E",
    # o'zbek alifbosida yo'q, lekin rus tilidan o'zlashgan so'zlarda
    # uchrashi mumkin bo'lgan harflar
    "ы": "i", "Ы": "I",
    "щ": "shch", "Щ": "Shch",
    "ь": "", "Ь": "",
}


def _transliterate_cyr_to_lat(text: str) -> str:
    return "".join(CYR_TO_LAT.get(ch, ch) for ch in text)


def kirill_to_lotin(text: str) -> str:
    """Matnni lotinga o'giradi, @username va linklarni o'zgartirmaydi."""
    if not text:
        return text
    parts = PROTECTED_RE.split(text)
    out = []
    for part in parts:
        if PROTECTED_RE.fullmatch(part or ""):
            out.append(part)
        else:
            out.append(_transliterate_cyr_to_lat(part))
    return "".join(out)


CYRILLIC_LETTER_RE = re.compile(r"[\u0400-\u04FF]")
LATIN_LETTER_RE = re.compile(r"[A-Za-z]")


def detect_script(text: str) -> str | None:
    """Matnda kirillcha harflar ko'pmi yoki lotincha — shuni aniqlaydi.
    Harflar umuman bo'lmasa None qaytaradi."""
    cyr_count = len(CYRILLIC_LETTER_RE.findall(text))
    lat_count = len(LATIN_LETTER_RE.findall(text))
    if cyr_count == 0 and lat_count == 0:
        return None
    return "cyrillic" if cyr_count >= lat_count else "latin"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# /start, /myid, /addadmin, /removeadmin, /listadmins — boshqaruv buyruqlari
# ---------------------------------------------------------------------------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(
            f"Kanalimizga e'lon berish uchun {CONTACT_USERNAME} ga yozing."
        )
        return
    await message.answer(
        "✅ Bot ishga tushdi.\n\n"
        "Bevosita menga matn yuborsangiz, krillcha bo'lsa lotinga, "
        "lotincha bo'lsa krillchaga o'girib beraman.\n\n"
        "Buyruqlar:\n"
        "/myid — ID'ingizni ko'rish\n"
        "/add — joriy guruh/kanalni ruxsat berilganlar ro'yxatiga qo'shish\n"
        "/removechat — joriy chatni ruxsat ro'yxatidan olib tashlash\n"
        "/chatid — joriy chat ID va holatini ko'rish\n"
        "/listchats — ruxsat berilgan chatlar ro'yxati\n"
        "/addadmin <user_id> — yangi admin qo'shish\n"
        "/removeadmin <user_id> — adminni o'chirish\n"
        "/listadmins — adminlar ro'yxati"
    )


@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>", parse_mode="HTML")


@dp.message(Command("addadmin"))
async def cmd_add_admin(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Foydalanish: /addadmin <user_id>")
        return
    new_id = int(args)
    admin_ids.add(new_id)
    save_admins()
    await message.answer(f"✅ {new_id} admin sifatida qo'shildi.")


@dp.message(Command("removeadmin"))
async def cmd_remove_admin(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    args = (command.args or "").strip()
    if not args.isdigit():
        await message.answer("Foydalanish: /removeadmin <user_id>")
        return
    rem_id = int(args)
    admin_ids.discard(rem_id)
    save_admins()
    await message.answer(f"🗑 {rem_id} adminlikdan olib tashlandi.")


@dp.message(Command("listadmins"))
async def cmd_list_admins(message: Message):
    if not is_admin(message.from_user.id):
        return
    if not admin_ids:
        await message.answer("Adminlar ro'yxati bo'sh.")
        return
    text = "\n".join(f"• <code>{uid}</code>" for uid in sorted(admin_ids))
    await message.answer(f"Adminlar:\n{text}", parse_mode="HTML")


# ---------------------------------------------------------------------------
# Admin botga shaxsiy xabar sifatida oddiy matn yuborsa: matn krillcha
# bo'lsa lotinga, lotincha bo'lsa krillchaga avtomatik o'girib beradi.
# ---------------------------------------------------------------------------

@dp.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def on_admin_plain_text(message: Message):
    if not is_admin(message.from_user.id):
        return

    script = detect_script(message.text)
    if script is None:
        return  # matnda harf yo'q (masalan faqat raqam/emoji) — tegilmaymiz

    if script == "cyrillic":
        converted = kirill_to_lotin(message.text)
    else:
        converted = lotin_to_kirill(message.text)

    await message.answer(converted)


# ---------------------------------------------------------------------------
# Bot biror chatga (kanal/guruh) qo'shilganda ishlaydigan handler.
# Bu yerda AVTOMATIK ruxsat berilmaydi — faqat xavfsizlik uchun: agar
# botni ADMIN_IDS'da bo'lmagan kishi qo'shsa, bot o'sha yerdan chiqib
# ketadi. Ruxsat berish endi qo'lda, guruhda /add buyrug'i orqali
# amalga oshiriladi (pastga qarang).
# ---------------------------------------------------------------------------

@dp.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated):
    new_status = update.new_chat_member.status
    actor_id = update.from_user.id if update.from_user else None
    chat = update.chat

    if new_status in ("administrator", "member"):
        if not is_admin(actor_id):
            logging.warning(
                "Ruxsatsiz foydalanuvchi (%s) botni '%s' (%s) chatga qo'shdi — chatdan chiqilmoqda",
                actor_id, chat.title, chat.id,
            )
            allowed_chats.discard(chat.id)
            save_allowed_chats()
            try:
                await bot.leave_chat(chat.id)
            except Exception:
                logging.exception("Chatdan chiqishda xatolik: %s", chat.id)
        else:
            logging.info(
                "Admin (%s) botni '%s' (%s) chatga qo'shdi. Ishlashi uchun "
                "o'sha chatda /add deb yozing.",
                actor_id, chat.title, chat.id,
            )
    elif new_status in ("left", "kicked"):
        allowed_chats.discard(chat.id)
        save_allowed_chats()


# ---------------------------------------------------------------------------
# Guruhga a'zo qo'shilgan/chiqqanda Telegram avtomatik chiqaradigan
# "... guruhga qo'shildi" / "... guruhdan chiqdi" degan tizim xabarlarini
# o'chirib, guruhni toza tutish
# ---------------------------------------------------------------------------

@dp.message(F.new_chat_members | F.left_chat_member)
async def on_membership_service_message(message: Message):
    if message.chat.id not in allowed_chats:
        return
    try:
        await message.delete()
    except Exception:
        logging.warning(
            "Qo'shildi/chiqdi xabarini o'chirib bo'lmadi (chat_id=%s) — "
            "botda 'Delete Messages' huquqi bormi tekshiring.",
            message.chat.id,
        )


# ---------------------------------------------------------------------------
# /add, /removechat, /listchats, /chatid — chatlarni qo'lda ruxsat berish
# ---------------------------------------------------------------------------

@dp.message(Command("add"))
async def cmd_add_chat(message: Message):
    """Guruh/kanalda admin shu buyruqni yozsa, o'sha chat bot uchun
    ishlaydigan chatlar ro'yxatiga qo'shiladi."""
    if not is_admin(message.from_user.id):
        return
    if message.chat.type == "private":
        await message.answer("Bu buyruqni bot ishlashi kerak bo'lgan guruh yoki kanalda yozing.")
        return
    allowed_chats.add(message.chat.id)
    save_allowed_chats()
    await message.answer(
        f"✅ Bu chat ruxsat berilganlar ro'yxatiga qo'shildi.\n"
        f"Chat: <b>{message.chat.title or message.chat.id}</b>\n"
        f"ID: <code>{message.chat.id}</code>",
        parse_mode="HTML",
    )


@dp.message(Command("removechat"))
async def cmd_remove_chat(message: Message):
    """Joriy chatni ruxsat berilganlar ro'yxatidan olib tashlaydi."""
    if not is_admin(message.from_user.id):
        return
    allowed_chats.discard(message.chat.id)
    save_allowed_chats()
    await message.answer("🗑 Bu chat ruxsat ro'yxatidan olib tashlandi.")


@dp.message(Command("chatid"))
async def cmd_chat_id(message: Message):
    status = "✅ ruxsat berilgan" if message.chat.id in allowed_chats else "⛔ ruxsat berilmagan"
    await message.answer(
        f"Chat ID: <code>{message.chat.id}</code>\nHolati: {status}",
        parse_mode="HTML",
    )


@dp.message(Command("listchats"))
async def cmd_list_chats(message: Message):
    if not is_admin(message.from_user.id):
        return
    if not allowed_chats:
        await message.answer("Ruxsat berilgan chatlar yo'q.")
        return
    text = "\n".join(f"• <code>{cid}</code>" for cid in sorted(allowed_chats))
    await message.answer(f"Ruxsat berilgan chatlar:\n{text}", parse_mode="HTML")


# ---------------------------------------------------------------------------
# Albom (n ta media) uchun: barcha qismlar kelguncha kutib, BITTA izoh
# sifatida (sendMediaGroup) joylashtirish
# ---------------------------------------------------------------------------

def _build_input_media(m: Message, caption: str | None):
    if m.photo:
        return InputMediaPhoto(media=m.photo[-1].file_id, caption=caption)
    if m.video:
        return InputMediaVideo(media=m.video.file_id, caption=caption)
    if m.document:
        return InputMediaDocument(media=m.document.file_id, caption=caption)
    if m.audio:
        return InputMediaAudio(media=m.audio.file_id, caption=caption)
    return None


async def flush_media_group(media_group_id: str):
    await asyncio.sleep(MEDIA_GROUP_DELAY)
    messages = pending_groups.pop(media_group_id, [])
    pending_tasks.pop(media_group_id, None)
    if not messages:
        return

    messages.sort(key=lambda m: m.message_id)

    original_caption = ""
    for m in messages:
        if m.caption:
            original_caption = m.caption
            break
    new_caption = _truncate(lotin_to_kirill(original_caption), CAPTION_LIMIT) or None

    media_list = []
    for i, m in enumerate(messages):
        item = _build_input_media(m, new_caption if i == 0 else None)
        if item is not None:
            media_list.append(item)

    if not media_list:
        return

    chat_id = messages[0].chat.id
    reply_to = messages[0].message_id
    try:
        await bot.send_media_group(
            chat_id=chat_id,
            media=media_list,
            reply_to_message_id=reply_to,
        )
    except Exception:
        logging.exception("Albom izohini yozishda xatolik")


# ---------------------------------------------------------------------------
# Asosiy handler: kanaldan guruhga avtomatik kelgan postni ushlash
# ---------------------------------------------------------------------------

@dp.message(F.is_automatic_forward == True)  # noqa: E712
async def on_channel_post(message: Message):
    # Faqat ruxsat berilgan (admin tomonidan qo'shilgan) chatlarda ishlaymiz
    if message.chat.id not in allowed_chats:
        logging.info("Ruxsat berilmagan chat (%s) — post e'tiborsiz qoldirildi", message.chat.id)
        return

    if message.media_group_id:
        gid = message.media_group_id
        pending_groups.setdefault(gid, []).append(message)
        if gid not in pending_tasks:
            pending_tasks[gid] = asyncio.create_task(flush_media_group(gid))
        return

    original = message.text or message.caption or ""
    new_text = lotin_to_kirill(original)

    try:
        if message.photo:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=message.photo[-1].file_id,
                caption=_truncate(new_text, CAPTION_LIMIT),
                reply_to_message_id=message.message_id,
            )
        elif message.video:
            await bot.send_video(
                chat_id=message.chat.id,
                video=message.video.file_id,
                caption=_truncate(new_text, CAPTION_LIMIT),
                reply_to_message_id=message.message_id,
            )
        elif message.animation:
            await bot.send_animation(
                chat_id=message.chat.id,
                animation=message.animation.file_id,
                caption=_truncate(new_text, CAPTION_LIMIT),
                reply_to_message_id=message.message_id,
            )
        elif message.document:
            await bot.send_document(
                chat_id=message.chat.id,
                document=message.document.file_id,
                caption=_truncate(new_text, CAPTION_LIMIT),
                reply_to_message_id=message.message_id,
            )
        elif new_text.strip():
            await bot.send_message(
                chat_id=message.chat.id,
                text=_truncate(new_text, TEXT_LIMIT),
                reply_to_message_id=message.message_id,
            )
    except Exception:
        logging.exception("Izoh yozishda xatolik")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Boshlang'ich adminlar: %s", admin_ids)
    logging.info("Ruxsat berilgan chatlar: %s", allowed_chats)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
