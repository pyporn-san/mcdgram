from pyrogram import filters

from common import app, bot_telegram_id


@app.on_message(filters.command(["lolibooru", f"lolibooru{bot_telegram_id}"]))
async def getLolibooru(client, message):
    await message.reply_text("kys pedophile")
