import aiosqlite
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

class Store:
    def __init__(self, path): self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, timezone TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, title TEXT NOT NULL, due_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS idx_due ON reminders(status, due_at);
            ''')
            async with db.execute('PRAGMA table_info(reminders)') as cur:
                columns = {row[1] for row in await cur.fetchall()}
            for name, definition in [('repeat_rule', "TEXT NOT NULL DEFAULT 'once'"), ('timezone', "TEXT NOT NULL DEFAULT 'Asia/Tehran'"), ('next_attempt', 'TEXT'), ('last_error', 'TEXT'), ('wall_time', 'TEXT')]:
                if name not in columns:
                    await db.execute(f'ALTER TABLE reminders ADD COLUMN {name} {definition}')
            async with db.execute('PRAGMA table_info(users)') as cur:
                user_columns = {row[1] for row in await cur.fetchall()}
            if 'language' not in user_columns:
                await db.execute("ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'fa'")
            await db.commit()

    async def language(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT language FROM users WHERE user_id=?', (user_id,)) as cur:
                row = await cur.fetchone()
                return row[0] if row else 'fa'

    async def set_language(self, user_id, language, default_tz):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT INTO users(user_id,timezone,language) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET language=excluded.language', (user_id, default_tz, language))
            await db.commit()

    async def timezone(self, user_id, default):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute('SELECT timezone FROM users WHERE user_id=?', (user_id,)) as c:
                row = await c.fetchone()
                return row[0] if row else default

    async def set_timezone(self, user_id, tz):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('INSERT INTO users(user_id,timezone) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET timezone=excluded.timezone', (user_id, tz)); await db.commit()

    async def add(self, user_id, chat_id, title, when, repeat='once', tz='Asia/Tehran'):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute('INSERT INTO reminders(user_id,chat_id,title,due_at,repeat_rule,timezone,wall_time) VALUES(?,?,?,?,?,?,?)', (user_id, chat_id, title, when.astimezone(timezone.utc).isoformat(), repeat, tz, when.astimezone(ZoneInfo(tz)).strftime('%H:%M:%S')))
            await db.commit(); return cur.lastrowid

    async def list(self, user_id, page=1):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT id,title,due_at,repeat_rule FROM reminders WHERE user_id=? AND status='pending' ORDER BY due_at LIMIT 10 OFFSET ?", (user_id, max(0, page-1)*10)) as cur: return await cur.fetchall()

    async def get(self, user_id, reminder_id):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT id FROM reminders WHERE user_id=? AND id=? AND status='pending'", (user_id, reminder_id)) as cur: return await cur.fetchone()

    async def failures(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT id,title FROM reminders WHERE user_id=? AND status='failed' ORDER BY id DESC LIMIT 50", (user_id,)) as cur: return await cur.fetchall()

    async def retry(self, user_id, rid):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("UPDATE reminders SET status='pending',attempts=0,next_attempt=NULL WHERE user_id=? AND id=? AND status='failed'", (user_id,rid))
            await db.commit(); return cur.rowcount == 1

    async def delete(self, user_id, reminder_id):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("UPDATE reminders SET status='cancelled' WHERE id=? AND user_id=? AND status IN ('pending','failed')", (reminder_id, user_id)); await db.commit(); return cur.rowcount == 1

    async def edit(self, user_id, reminder_id, title, when, tz):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("UPDATE reminders SET title=?,due_at=?,timezone=?,wall_time=?,attempts=0,next_attempt=NULL WHERE id=? AND user_id=? AND status='pending'", (title, when.astimezone(timezone.utc).isoformat(), tz, when.astimezone(ZoneInfo(tz)).strftime('%H:%M:%S'), reminder_id, user_id))
            await db.commit(); return cur.rowcount == 1

    async def due(self):
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT id,chat_id,title,due_at,repeat_rule,timezone,attempts,user_id FROM reminders WHERE status='pending' AND due_at<=? AND (next_attempt IS NULL OR next_attempt<=?) ORDER BY due_at LIMIT 100", (now, now)) as cur: return await cur.fetchall()

    async def sent(self, rid, due, repeat, tz):
        async with aiosqlite.connect(self.path) as db:
            if repeat == 'once':
                await db.execute("UPDATE reminders SET status='sent' WHERE id=? AND status='pending' AND due_at=?", (rid, due))
            else:
                async with db.execute("SELECT wall_time FROM reminders WHERE id=?", (rid,)) as cur:
                    row = await cur.fetchone()
                zone = ZoneInfo(tz)
                original = datetime.fromisoformat(due).astimezone(zone)
                wall = row[0] if row and row[0] else original.strftime('%H:%M:%S')
                h, minute, sec = map(int, wall.split(':'))
                now = datetime.now(timezone.utc)
                days = 1 if repeat == 'daily' else 7
                day = original.date()
                while True:
                    day += timedelta(days=days)
                    candidate = datetime(day.year, day.month, day.day, h, minute, sec, tzinfo=zone, fold=0)
                    # Round-trip through UTC to resolve a nonexistent wall time forward.
                    candidate = candidate.astimezone(timezone.utc).astimezone(zone)
                    if candidate.astimezone(timezone.utc) > now:
                        break
                await db.execute("UPDATE reminders SET due_at=?,wall_time=?,attempts=0,next_attempt=NULL WHERE id=? AND status='pending' AND due_at=?", (candidate.astimezone(timezone.utc).isoformat(), wall, rid, due))
            await db.commit()

    async def failed(self, rid, attempts, due=None, permanent=False):
        attempts += 1
        retry = (datetime.now(timezone.utc) + timedelta(seconds=min(3600, 30 * 2 ** min(attempts-1, 7)))).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE reminders SET attempts=?,next_attempt=?,status=? WHERE id=? AND status='pending' AND (? IS NULL OR due_at=?)", (attempts, retry, 'failed' if permanent or attempts >= 10 else 'pending', rid, due, due))
            await db.commit()

    async def defer(self, rid, due, seconds):
        retry = (datetime.now(timezone.utc) + timedelta(seconds=max(1, seconds))).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE reminders SET next_attempt=? WHERE id=? AND status='pending' AND due_at=?", (retry, rid, due))
            await db.commit()
