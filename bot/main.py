import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

from bot.db import Database
from bot.settings import settings
from bot.nlp import nl_to_sql

logging.basicConfig(level=logging.INFO)

db = Database()


async def on_text(message: Message) -> None:
    q = (message.text or "").strip()
    if not q:
        return

    try:
        sql = await nl_to_sql(q)
        num = await db.fetch_number(sql)
        await message.answer(str(num))
    except Exception as e:
        logging.exception("Failed to answer: %s", e)
        await message.answer("0")


async def main() -> None:
    await db.connect()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.message.register(on_text, F.text)

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())