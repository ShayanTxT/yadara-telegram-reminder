import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage
from aiogram.types import Update
from aiogram.client.session.base import BaseSession
from datetime import datetime
import yadara.__main__ as app
from yadara.storage import Store

class MockSession(BaseSession):
    def __init__(self):
        super().__init__(); self.messages = []
    async def close(self): pass
    async def make_request(self, bot, method, timeout=None):
        if isinstance(method, SendMessage):
            self.messages.append(method.text)
            return True
    async def stream_content(self, *args, **kwargs):
        if False: yield b''

@pytest.mark.asyncio
async def test_full_flow(tmp_path, monkeypatch):
    store = Store(str(tmp_path / 'test.db')); await store.init()
    monkeypatch.setattr(app, 'store', store)
    session = MockSession(); bot = Bot('123456:ABCDEFabcdef1234567890ABCDEFabcdef', session=session)
    dp = Dispatcher(); dp.include_router(app.router)
    async def send(text, n):
        update = Update.model_validate({'update_id': n, 'message': {'message_id': n, 'date': int(datetime.now().timestamp()), 'chat': {'id': 42, 'type': 'private'}, 'from': {'id': 42, 'is_bot': False, 'first_name': 'Test'}, 'text': text}})
        await dp.feed_update(bot, update)
    try:
        await send('فردا ساعت ۳ عصر قرص بخورم', 1)
        assert 'چند بار' in session.messages[-1]
        await send('یک‌بار', 2)
        assert 'تأیید' in session.messages[-1]
        assert not await store.list(42)
        await send('✅ تأیید', 3)
        assert len(await store.list(42)) == 1
        await send('/delete 1', 4)
        assert not await store.list(42)
    finally:
        app.router._parent_router = None
        await bot.session.close()

@pytest.mark.asyncio
async def test_english_flow(tmp_path, monkeypatch):
    store = Store(str(tmp_path / 'test.db')); await store.init()
    monkeypatch.setattr(app, 'store', store)
    session = MockSession(); bot = Bot('123456:ABCDEFabcdef1234567890ABCDEFabcdef', session=session)
    dp = Dispatcher(); dp.include_router(app.router)
    async def send(text, n):
        update = Update.model_validate({'update_id': n, 'message': {'message_id': n, 'date': int(datetime.now().timestamp()), 'chat': {'id': 42, 'type': 'private'}, 'from': {'id': 42, 'is_bot': False, 'first_name': 'Test'}, 'text': text}})
        await dp.feed_update(bot, update)
    try:
        await send('/language en', 1)
        assert 'English' in session.messages[-1]
        await send('remind me to call mom tomorrow at 3 pm', 2)
        assert 'How often' in session.messages[-1]
        await send('Daily', 3)
        assert 'Confirm?' in session.messages[-1]
        await send('✅ Confirm', 4)
        assert 'Saved' in session.messages[-1]
        assert (await store.list(42))[0][1] == 'call mom'
        await send('/language fa', 5)
        assert await store.language(42) == 'fa'
    finally:
        app.router._parent_router = None
        await bot.session.close()
