from datetime import datetime
from zoneinfo import ZoneInfo
from yadara.parser import parse

NOW = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo('Asia/Tehran'))

def test_persian():
    p = parse('فردا ساعت ۳ عصر قرص بخورم', NOW)
    assert p.title == 'قرص بخورم'
    assert (p.when.day, p.when.hour) == (2, 15)

def test_ambiguous():
    assert 'مبهم' in parse('فردا ساعت ۳ قرص', NOW).error

def test_24_hour():
    assert parse('پس فردا ساعت ۱۵:۳۰ جلسه', NOW).when.hour == 15

def test_past():
    assert 'گذشته' in parse('امروز ساعت ۹ صبح قرص', NOW).error

def test_invalid():
    assert parse('فردا ساعت 25:99 کار', NOW).error

def test_jalali():
    result = parse('۱۴۰۴/۱۰/۱۲ ساعت ۱۵:۳۰ جلسه', NOW)
    assert result.when.date().isoformat() == '2026-01-02'
    assert result.title == 'جلسه'

def test_invalid_jalali():
    assert parse('۱۴۰۴/۱۳/۱ ساعت ۱۵ کار', NOW).error

def test_dst_ambiguous():
    now = datetime(2026, 10, 24, 10, tzinfo=ZoneInfo('Europe/London'))
    assert 'مبهم' in parse('فردا ساعت ۱:۳۰ صبح کار', now).error

def test_midnight():
    assert parse('فردا ساعت ۱۲ شب قرص', NOW).when.hour == 0
    assert parse('فردا ساعت ۱۲ عصر قرص', NOW).when.hour == 12

def test_dst_nonexistent():
    now = datetime(2026, 3, 28, 10, tzinfo=ZoneInfo('Europe/London'))
    assert 'ناموجود' in parse('فردا ساعت ۱:۳۰ صبح کار', now).error

def test_english_relative_and_iso():
    from yadara.parser import parse_english
    p = parse_english('remind me to take medicine tomorrow at 3 pm', NOW)
    assert p.title == 'take medicine' and p.when.hour == 15 and p.when.day == 2
    p = parse_english('2026-01-03 at 15:30 meeting', NOW)
    assert p.title == 'meeting' and p.when.day == 3

def test_english_ambiguity():
    from yadara.parser import parse_english
    assert 'ambiguous' in parse_english('tomorrow at 3 medicine', NOW).error
