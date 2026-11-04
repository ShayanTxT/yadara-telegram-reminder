import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import jdatetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from yadara.parser import parse, parse_english
from yadara.storage import Store

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN', '')
DEFAULT_TZ = os.getenv('DEFAULT_TIMEZONE', 'Asia/Tehran')
PATH = os.getenv('DATABASE_PATH', 'data/yadara.db')
INTERVAL = int(os.getenv('POLL_INTERVAL_SECONDS', '15'))
store = Store(PATH)
router = Router()
router.message.filter(F.chat.type == 'private')

def keyboard(*rows):
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in row] for row in rows], resize_keyboard=True)

def menu(lang): return keyboard(['➕ یادآوری جدید', '📋 یادآوری‌های من'] if lang == 'fa' else ['➕ New reminder', '📋 My reminders'])
def confirm_menu(lang): return keyboard(['✅ تأیید', '❌ لغو'] if lang == 'fa' else ['✅ Confirm', '❌ Cancel'])
def repeat_menu(lang): return keyboard(['یک‌بار', 'روزانه', 'هفتگی'] if lang == 'fa' else ['Once', 'Daily', 'Weekly'], ['❌ لغو' if lang == 'fa' else '❌ Cancel'])
REPEATS = {'یک‌بار': 'once', 'روزانه': 'daily', 'هفتگی': 'weekly', 'Once': 'once', 'Daily': 'daily', 'Weekly': 'weekly'}
LABELS = {'fa': {'once': 'یک‌بار', 'daily': 'روزانه', 'weekly': 'هفتگی'}, 'en': {'once': 'Once', 'daily': 'Daily', 'weekly': 'Weekly'}}

def tr(lang, fa, en): return fa if lang == 'fa' else en
async def lang(m): return await store.language(m.from_user.id)
async def timezone_for(m): return ZoneInfo(await store.timezone(m.from_user.id, DEFAULT_TZ))
def format_date(dt, language):
    if language == 'en': return f'{dt:%Y-%m-%d %H:%M} ({dt.tzinfo})'
    jd = jdatetime.date.fromgregorian(date=dt.date())
    return f'{jd.year:04}/{jd.month:02}/{jd.day:02}، {dt:%H:%M} ({dt.tzinfo})'
def id_args(m):
    parts = (m.text or '').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')).split()
    if len(parts) != 2 or not parts[1].isdigit() or len(parts[1]) > 18: return None
    return int(parts[1])

class Create(StatesGroup):
    title = State()
    time = State()
    repeat = State()
    confirm = State()

@router.message(Command('language'))
async def language_command(m: Message, state: FSMContext):
    parts = (m.text or '').split()
    if len(parts) != 2 or parts[1].lower() not in ('fa', 'en'):
        return await m.answer('زبان / Language: /language fa | /language en')
    language = parts[1].lower()
    await store.set_language(m.from_user.id, language, DEFAULT_TZ)
    await state.clear()
    await m.answer(tr(language, 'زبان به فارسی تغییر کرد.', 'Language set to English.'), reply_markup=menu(language))

@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear(); l = await lang(m)
    await m.answer(tr(l, 'سلام! من یادآرا هستم 🌱\nبنویس: فردا ساعت ۳ عصر قرص بخورم\nیا از دکمه‌ها استفاده کن. /help\nبرای موارد حیاتی مثل دارو فقط به ربات تکیه نکن.\nEnglish: /language en', 'Hello! I am Yadara 🌱\nTry: remind me to take medicine tomorrow at 3 pm\nOr use the buttons. /help\nDo not rely solely on this bot for critical reminders.\nفارسی: /language fa'), reply_markup=menu(l))

@router.message(Command('help'))
async def help_command(m: Message):
    l = await lang(m)
    await m.answer(tr(l, 'مثال: فردا ساعت ۳ عصر قرص بخورم\nروزها: امروز، امشب، فردا، پس‌فردا یا تاریخ شمسی ۱۴۰۵/۰۸/۱۵.\nساعت ۱ تا ۱۲ را با صبح، عصر یا شب بنویس.', 'Example: remind me to take medicine tomorrow at 3 pm\nSupported dates: today, tomorrow or ISO date 2027-05-16.\nFor hours 1–12 specify am or pm.') + '\n\n/language fa | /language en\n/list [page]\n/edit 123\n/delete 123\n/failed\n/retry 123\n/timezone Europe/London\n/cancel')

@router.message(Command('cancel'))
@router.message(F.text.in_({'❌ لغو', '❌ Cancel'}))
async def cancel(m: Message, state: FSMContext):
    l = await lang(m); await state.clear(); await m.answer(tr(l, 'عملیات لغو شد.', 'Cancelled.'), reply_markup=menu(l))

@router.message(Command('timezone'))
async def set_tz(m: Message):
    l = await lang(m); parts = (m.text or '').split(maxsplit=1)
    if len(parts) != 2: return await m.answer(tr(l, 'منطقه زمانی فعلی:', 'Current time zone:') + f' {(await timezone_for(m)).key}\n/timezone Europe/London')
    try: ZoneInfo(parts[1])
    except (ZoneInfoNotFoundError, ValueError): return await m.answer(tr(l, 'منطقه زمانی معتبر نیست.', 'Invalid time zone.'))
    await store.set_timezone(m.from_user.id, parts[1])
    await m.answer(tr(l, 'تنظیم شد. یادآوری‌های قبلی زمان و منطقه خود را حفظ می‌کنند.', 'Time zone updated. Existing reminders keep their original schedule and time zone.'))

@router.message(Command('delete'))
async def delete(m: Message):
    l = await lang(m); rid = id_args(m)
    if rid is None: return await m.answer('Example / مثال: /delete 123')
    ok = await store.delete(m.from_user.id, rid)
    await m.answer(tr(l, 'حذف شد.' if ok else 'یادآوری پیدا نشد.', 'Deleted.' if ok else 'Reminder not found.'))

@router.message(Command('list'))
@router.message(F.text.in_({'📋 یادآوری‌های من', '📋 My reminders'}))
async def list_reminders(m: Message):
    l = await lang(m); parts = (m.text or '').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')).split()
    page = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) < 7 else 1
    if page < 1 or page > 100000: return await m.answer(tr(l, 'شماره صفحه نامعتبر است.', 'Invalid page.'))
    rows = await store.list(m.from_user.id, page)
    if not rows: return await m.answer(tr(l, 'یادآوری فعالی در این صفحه نداری.', 'No active reminders on this page.'))
    tz = await timezone_for(m)
    for i,title,d,r in rows: await m.answer(f'#{i} | {format_date(datetime.fromisoformat(d).astimezone(tz), l)} | {LABELS[l][r]} | {title}')
    await m.answer(tr(l, f'صفحه {page}؛ صفحه بعد: /list {page+1}\nحذف: /delete شناسه\nویرایش: /edit شناسه', f'Page {page}; next: /list {page+1}\nDelete: /delete ID\nEdit: /edit ID'))

@router.message(Command('failed'))
async def failed_list(m: Message):
    l = await lang(m); rows = await store.failures(m.from_user.id)
    if not rows: return await m.answer(tr(l, 'ارسال ناموفقی نداری.', 'No failed reminders.'))
    for rid,title in rows: await m.answer(f'#{rid} | {title}')
    await m.answer(tr(l, 'تلاش دوباره: /retry شناسه ؛ حذف: /delete شناسه', 'Retry: /retry ID; delete: /delete ID'))

@router.message(Command('retry'))
async def retry(m: Message):
    l = await lang(m); rid = id_args(m)
    if rid is None: return await m.answer('Example / مثال: /retry 123')
    ok = await store.retry(m.from_user.id, rid)
    await m.answer(tr(l, 'برای ارسال مجدد ثبت شد.' if ok else 'یادآوری ناموفق پیدا نشد.', 'Queued for retry.' if ok else 'Failed reminder not found.'))

@router.message(Command('edit'))
async def edit_start(m: Message, state: FSMContext):
    l = await lang(m); rid = id_args(m)
    if rid is None: return await m.answer('Example / مثال: /edit 123')
    if not await store.get(m.from_user.id, rid): return await m.answer(tr(l, 'یادآوری فعال پیدا نشد.', 'Active reminder not found.'))
    await state.clear(); await state.update_data(edit_id=rid); await state.set_state(Create.title)
    await m.answer(tr(l, 'موضوع جدید را بنویس. تکرار فعلی حفظ می‌شود.', 'Enter the new title. The recurrence will be preserved.'), reply_markup=ReplyKeyboardRemove())

@router.message(F.text.in_({'➕ یادآوری جدید', '➕ New reminder'}))
async def begin(m: Message, state: FSMContext):
    l = await lang(m); await state.clear(); await state.set_state(Create.title)
    await m.answer(tr(l, 'موضوع یادآوری چیه؟', 'What would you like to be reminded about?'), reply_markup=ReplyKeyboardRemove())

@router.message(Create.title, F.text)
async def title_step(m: Message, state: FSMContext):
    l = await lang(m); title = m.text.strip()
    if not title or len(title) > 300: return await m.answer(tr(l, 'موضوع باید بین ۱ تا ۳۰۰ نویسه باشد.', 'The title must be 1–300 characters.'))
    await state.update_data(title=title); await state.set_state(Create.time)
    await m.answer(tr(l, 'چه زمانی؟ مثلاً «فردا ساعت ۳ عصر» یا «۱۴۰۵/۰۸/۱۵ ساعت ۱۵:۳۰»', 'When? For example: tomorrow at 3 pm or 2027-05-16 at 15:30.'))

async def ask_repeat_or_confirm(m, state, when, title):
    l = await lang(m); await state.update_data(title=title, when=when.isoformat(), tz=(await timezone_for(m)).key)
    data = await state.get_data()
    if data.get('edit_id'):
        await state.set_state(Create.confirm)
        await m.answer(tr(l, f'موضوع: {title}\nزمان: {format_date(when,l)}\nتکرار قبلی حفظ می‌شود. تأیید می‌کنی؟', f'Title: {title}\nTime: {format_date(when,l)}\nRecurrence is unchanged. Confirm?'), reply_markup=confirm_menu(l))
    else:
        await state.set_state(Create.repeat)
        await m.answer(tr(l, 'یادآوری چند بار تکرار شود؟', 'How often should this reminder repeat?'), reply_markup=repeat_menu(l))

@router.message(Create.time, F.text)
async def time_step(m: Message, state: FSMContext):
    l = await lang(m); data = await state.get_data(); now = datetime.now(await timezone_for(m))
    result = parse(m.text + ' موضوع', now) if l == 'fa' else parse_english(m.text + ' placeholder', now)
    if result.error: return await m.answer(result.error)
    await ask_repeat_or_confirm(m, state, result.when, data['title'])

@router.message(Create.repeat, F.text)
async def repeat_step(m: Message, state: FSMContext):
    l = await lang(m)
    if m.text not in REPEATS: return await m.answer(tr(l, 'یکی از گزینه‌ها را انتخاب کن.', 'Please choose an option.'), reply_markup=repeat_menu(l))
    await state.update_data(repeat=REPEATS[m.text]); data = await state.get_data(); await state.set_state(Create.confirm)
    when = datetime.fromisoformat(data['when']).astimezone(ZoneInfo(data['tz']))
    await m.answer(tr(l, f"موضوع: {data['title']}\nزمان: {format_date(when,l)}\nتکرار: {LABELS[l][data['repeat']]}\nتأیید می‌کنی؟", f"Title: {data['title']}\nTime: {format_date(when,l)}\nRepeat: {LABELS[l][data['repeat']]}\nConfirm?"), reply_markup=confirm_menu(l))

@router.message(Create.confirm, F.text.in_({'✅ تأیید', '✅ Confirm'}))
async def confirm(m: Message, state: FSMContext):
    l = await lang(m); data = await state.get_data(); when = datetime.fromisoformat(data['when'])
    if when <= datetime.now(when.tzinfo):
        await state.clear(); return await m.answer(tr(l, 'زمان گذشته؛ دوباره ثبت کن.', 'That time has passed. Please start again.'), reply_markup=menu(l))
    if data.get('edit_id'):
        ok = await store.edit(m.from_user.id, data['edit_id'], data['title'], when, data['tz'])
        msg = tr(l, 'تغییرات ذخیره شد ✅' if ok else 'یادآوری دیگر فعال نیست.', 'Changes saved ✅' if ok else 'Reminder is no longer active.')
    else:
        rid = await store.add(m.from_user.id, m.chat.id, data['title'], when, data['repeat'], data['tz'])
        msg = tr(l, f'ثبت شد ✅ شناسه: {rid}', f'Saved ✅ ID: {rid}')
    await state.clear(); await m.answer(msg, reply_markup=menu(l))

@router.message(Create.confirm)
async def confirm_invalid(m: Message):
    l = await lang(m); await m.answer(tr(l, 'لطفاً تأیید یا لغو را انتخاب کن.', 'Please choose confirm or cancel.'))

@router.message(F.text)
async def natural(m: Message, state: FSMContext):
    l = await lang(m); now = datetime.now(await timezone_for(m))
    result = parse(m.text, now) if l == 'fa' else parse_english(m.text, now)
    if result.error: return await m.answer(result.error + tr(l, '\nمی‌توانی از دکمه ثبت مرحله‌ای استفاده کنی.', '\nYou can use the guided reminder button.'), reply_markup=menu(l))
    await state.clear(); await ask_repeat_or_confirm(m, state, result.when, result.title)

async def scheduler(bot):
    while True:
        try:
            for rid, chat_id, title, due, repeat, tz, attempts, user_id in await store.due():
                try:
                    l = await store.language(user_id)
                    await bot.send_message(chat_id, tr(l, f'🔔 یادآوری: {title}', f'🔔 Reminder: {title}'))
                    await store.sent(rid, due, repeat, tz)
                except TelegramRetryAfter as exc:
                    logging.warning('Telegram rate limit on reminder %s', rid); await store.defer(rid, due, exc.retry_after)
                except (TelegramForbiddenError, TelegramBadRequest):
                    logging.warning('Permanent delivery failure for reminder %s', rid); await store.failed(rid, attempts, due, permanent=True)
                except Exception:
                    logging.warning('Temporary delivery failure for reminder %s', rid); await store.failed(rid, attempts, due)
        except Exception: logging.exception('Scheduler error')
        await asyncio.sleep(INTERVAL)

async def main():
    if not TOKEN or TOKEN == 'your_telegram_bot_token': raise RuntimeError('Set BOT_TOKEN in .env')
    ZoneInfo(DEFAULT_TZ)
    if INTERVAL < 1: raise ValueError('POLL_INTERVAL_SECONDS must be positive')
    Path(PATH).parent.mkdir(parents=True, exist_ok=True); await store.init()
    bot = Bot(TOKEN); dp = Dispatcher(); dp.include_router(router)
    task = asyncio.create_task(scheduler(bot))
    try: await dp.start_polling(bot)
    finally:
        task.cancel(); await asyncio.gather(task, return_exceptions=True); await bot.session.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
