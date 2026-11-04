"""Conservative Persian date parser: never guesses ambiguous times."""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import jdatetime

DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')

@dataclass
class Parsed:
    title: str
    when: datetime | None
    error: str | None = None

def parse(text: str, now: datetime) -> Parsed:
    s = text.translate(DIGITS).replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ').strip()
    day = re.search(r'پس\s*فردا|فردا|امروز|امشب|(?<!\d)1[34]\d{2}[/\-]\d{1,2}[/\-]\d{1,2}(?!\d)', s)
    if not day:
        return Parsed('', None, 'روز را مشخص کن؛ مثلاً فردا یا تاریخ شمسی ۱۴۰۵/۰۸/۱۵.')
    remaining = s[:day.start()] + ' ' * (day.end() - day.start()) + s[day.end():]
    clock = re.search(r'(?:ساعت\s*)?(?<!\d)(\d{1,2})(?::(\d{2}))?(?!\d)\s*(صبح|عصر|بعد\s*از\s*ظهر|شب|بامداد)?', remaining)
    if not clock:
        return Parsed('', None, 'ساعت را مشخص کن؛ مثلاً ساعت ۳ عصر.')
    hour, minute = int(clock.group(1)), int(clock.group(2) or 0)
    period = clock.group(3)
    if hour > 23 or minute > 59:
        return Parsed('', None, 'ساعت نامعتبر است.')
    if not period and 1 <= hour <= 12:
        return Parsed('', None, 'ساعت مبهم است؛ لطفاً صبح، عصر یا شب را مشخص کن.')
    if period:
        if not 1 <= hour <= 12:
            return Parsed('', None, 'با صبح یا عصر، ساعت را بین ۱ تا ۱۲ بنویس.')
        hour = hour % 12 + (12 if period in ('عصر', 'بعد از ظهر', 'بعدازظهر') or (period == 'شب' and hour != 12) else 0)
    token = day.group().replace(' ', '')
    try:
        if re.match(r'1[34]\d{2}', token):
            y, mo, d = map(int, re.split(r'[/\-]', token))
            date = jdatetime.date(y, mo, d).togregorian()
        else:
            offset = 2 if token == 'پسفردا' else 1 if token == 'فردا' else 0
            date = (now + timedelta(days=offset)).date()
        naive = datetime(date.year, date.month, date.day, hour, minute)
    except ValueError:
        return Parsed('', None, 'تاریخ نامعتبر است.')
    # Reject nonexistent and ambiguous wall-clock times rather than silently guessing.
    a, b = naive.replace(tzinfo=now.tzinfo, fold=0), naive.replace(tzinfo=now.tzinfo, fold=1)
    valid = [x for x in (a, b) if x.astimezone(timezone.utc).astimezone(now.tzinfo).replace(tzinfo=None) == naive]
    if not valid or (len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset()):
        return Parsed('', None, 'این ساعت به دلیل تغییر ساعت منطقه زمانی ناموجود یا مبهم است؛ ساعت دیگری انتخاب کن.')
    when = valid[0]
    if when <= now:
        return Parsed('', None, 'این زمان گذشته است؛ زمان دیگری انتخاب کن.')
    title = s
    for start, end in sorted([day.span(), clock.span()], reverse=True):
        title = title[:start] + ' ' + title[end:]
    title = re.sub(r'(?:بهم|به من|یادم بنداز|یادآوری کن|یادآوری)', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip(' ،,.!')
    if not title:
        return Parsed('', None, 'موضوع یادآوری را هم بنویس.')
    if len(title) > 300:
        return Parsed('', None, 'موضوع نباید بیش از ۳۰۰ نویسه باشد.')
    return Parsed(title, when)

def parse_english(text: str, now: datetime) -> Parsed:
    """Recognize explicit English relative days or ISO dates and numeric times."""
    s = text.strip()
    day = re.search(r'\b(?:today|tomorrow|\d{4}-\d{2}-\d{2})\b', s, re.I)
    if not day:
        return Parsed('', None, 'Specify today, tomorrow, or an ISO date like 2027-05-16.')
    remaining = s[:day.start()] + ' ' * (day.end() - day.start()) + s[day.end():]
    clock = re.search(r'\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', remaining, re.I)
    if not clock: return Parsed('', None, 'Specify a time, for example 3 pm or 15:30.')
    hour, minute = int(clock.group(1)), int(clock.group(2) or 0)
    period = (clock.group(3) or '').lower()
    if hour > 23 or minute > 59: return Parsed('', None, 'Invalid time.')
    if not period and 1 <= hour <= 12: return Parsed('', None, 'That time is ambiguous; please specify am or pm.')
    if period:
        if not 1 <= hour <= 12: return Parsed('', None, 'Use a 1–12 hour with am or pm.')
        hour = hour % 12 + (12 if period == 'pm' else 0)
    try:
        token = day.group().lower()
        date = (now + timedelta(days=1 if token == 'tomorrow' else 0)).date() if token in ('today', 'tomorrow') else datetime.strptime(token, '%Y-%m-%d').date()
        naive = datetime(date.year, date.month, date.day, hour, minute)
    except ValueError: return Parsed('', None, 'Invalid date.')
    a, b = (naive.replace(tzinfo=now.tzinfo, fold=i) for i in (0, 1))
    valid = [x for x in (a,b) if x.astimezone(timezone.utc).astimezone(now.tzinfo).replace(tzinfo=None) == naive]
    if not valid or (len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset()): return Parsed('', None, 'This local time is ambiguous or does not exist. Choose another time.')
    when = valid[0]
    if when <= now: return Parsed('', None, 'This time is in the past.')
    title = s
    for start, end in sorted([day.span(), clock.span()], reverse=True): title = title[:start] + ' ' + title[end:]
    title = re.sub(r'\b(?:remind\s+me\s+to|remind\s+me|please)\b', ' ', title, flags=re.I)
    title = re.sub(r'\s+', ' ', title).strip(' ,.!')
    if not title: return Parsed('', None, 'Please include a reminder title.')
    if len(title) > 300: return Parsed('', None, 'The title must be at most 300 characters.')
    return Parsed(title, when)
