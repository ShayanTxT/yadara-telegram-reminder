from datetime import datetime, timedelta, timezone
import pytest
from yadara.storage import Store

@pytest.mark.asyncio
async def test_ownership_and_persistence(tmp_path):
    s = Store(str(tmp_path / 'test.db')); await s.init()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    rid = await s.add(1, 1, 'task', future)
    assert not await s.delete(2, rid)
    assert not await s.edit(2, rid, 'other', future, 'UTC')
    s2 = Store(s.path); await s2.init()
    assert (await s2.list(1))[0][1] == 'task'
    assert await s2.edit(1, rid, 'updated', future, 'UTC')
    assert (await s2.list(1))[0][1] == 'updated'
    assert await s2.delete(1, rid)
    assert not await s2.list(1)

@pytest.mark.asyncio
async def test_overdue_and_retry(tmp_path):
    s = Store(str(tmp_path / 'test.db')); await s.init()
    past = datetime.now(timezone.utc) - timedelta(days=2)
    rid = await s.add(1, 1, 'task', past, 'daily', 'UTC')
    rows = await s.due(); assert rows[0][0] == rid
    await s.failed(rid, 0)
    assert not await s.due()
    await s.sent(rid, rows[0][3], 'daily', 'UTC')
    rows = await s.list(1)
    assert datetime.fromisoformat(rows[0][2]) > datetime.now(timezone.utc)

@pytest.mark.asyncio
async def test_migration_existing_db(tmp_path):
    import aiosqlite
    path = str(tmp_path / 'old.db')
    async with aiosqlite.connect(path) as db:
        await db.execute("CREATE TABLE reminders (id INTEGER PRIMARY KEY, user_id INTEGER, chat_id INTEGER, title TEXT, due_at TEXT, status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0)")
        await db.commit()
    s = Store(path); await s.init()
    assert not await s.list(1)

@pytest.mark.asyncio
async def test_failed_retry_permissions(tmp_path):
    s = Store(str(tmp_path / 'test.db')); await s.init()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    rid = await s.add(1, 1, 'private', past)
    row = (await s.due())[0]
    await s.failed(rid, 0, row[3], permanent=True)
    assert len(await s.failures(1)) == 1
    assert not await s.retry(2, rid)
    assert await s.retry(1, rid)
    assert (await s.due())[0][0] == rid

@pytest.mark.asyncio
async def test_pages(tmp_path):
    s = Store(str(tmp_path / 'test.db')); await s.init()
    due = datetime.now(timezone.utc) + timedelta(hours=1)
    for i in range(12): await s.add(1, 1, str(i), due)
    assert len(await s.list(1, 1)) == 10
    assert len(await s.list(1, 2)) == 2

@pytest.mark.asyncio
async def test_language_and_timezone_independent(tmp_path):
    s = Store(str(tmp_path / 'test.db')); await s.init()
    assert await s.language(8) == 'fa'
    await s.set_language(8, 'en', 'Asia/Tehran')
    await s.set_timezone(8, 'Europe/London')
    assert await s.language(8) == 'en'
    assert await s.timezone(8, 'UTC') == 'Europe/London'
    await s.set_language(8, 'fa', 'UTC')
    assert await s.timezone(8, 'UTC') == 'Europe/London'
