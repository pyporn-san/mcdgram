from pyrogram import filters, idle, types
from pyrogram.errors import QueryIdInvalid
from telegraph import TelegraphException

from modules import *
from common import app, bot_telegram_id, logo_url, owner_id

newUsers = set()


@app.on_message(filters.regex(r"^\/"), group=-1)
async def logger(client, message):
    newUsers.add((message.from_user.id,
                  f"{message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name else ''}", f"@{message.from_user.username}"))
    if(message.from_user.id != 80244858):
        await app.send_message(-1001398894102, text=f"{message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name else ''}: {message.text}")


@app.on_message(filters.command(["status", f"status{bot_telegram_id}"]))
async def status(client, message):
    if(message.from_user.id == 80244858):
        await message.reply_text("\n".join([repr(usr) for usr in newUsers]))
    else:
        await message.reply_text("Private information")


@app.on_message(filters.command(["start", f"start{bot_telegram_id}"]))
def welcome(client, message):
    message.reply_text(f"Welcome, {message.from_user.first_name}!\
        \n\nThis is a NSFW bot made to access various Rule34 and Hentai websites\
        \nTo see usage details for each command, simply send the command without any arguments\
        \n\nCurrent supported websites are:\
        \n/danbooru (danbooru.donmai.us)\
        \n/gelbooru (gelbooru.com)\
        \n/rule34 (rule34.xxx)\
        \n/nhentai (nhentai.net)\
        \n/multporn (multporn.net)\
        \n/luscious (luscious.net)")


@app.on_inline_query(group=-1)
async def answerInline(client, inline_query):
    newUsers.add((inline_query.from_user.id,
                  f"{inline_query.from_user.first_name} {inline_query.from_user.last_name if inline_query.from_user.last_name else ''}", f"@{inline_query.from_user.username}"))
    if(inline_query.from_user.id != 80244858):
        await app.send_message(-1001398894102, text=f"{inline_query.from_user.first_name} {inline_query.from_user.last_name if inline_query .from_user.last_name else ''}: {bot_telegram_id} {inline_query.query}")


@app.on_inline_query()
async def answerInline(client, inline_query):
    try:
        await inline_query.answer([types.InlineQueryResultArticle(title="Click here for help", thumb_url=logo_url,
                                                                  input_message_content=types.InputTextMessageContent(f"The format for inline use is\
                                                                                                                        {bot_telegram_id} `source` query\
                                                                                                                        options for source are:\
                                                                                                                        gel - for gelbooru.com\
                                                                                                                        dan - for danbooru.donmai.us (limited to only 2 tags)\
                                                                                                                        rul - for rule34.xxx\n\
                                                                                                                        nhe - for nhentai.net\
                                                                                                                        lus - for luscious.net\n\
                                                                                                                        The first three are image boards and the query must be in the format of tags\
                                                                                                                        Tags are seperated by space and any space in the tags is replaced with '_'\
                                                                                                                        Tag example:\
                                                                                                                        bunny_girl fubuki_(one-punch_man)")
                                                                  )], cache_time=5)
    except:
        pass

# End region pyrogram handlers
app.start()
app.send_message(owner_id, "Starting")
print("Starting")
idle()
app.send_message(
    owner_id, f"Stopping\nNew users since last reboot = {len(newUsers)}\n{chr(10).join([repr(usr) for usr in newUsers])}")
print(
    f"Stopping\nNew users since last reboot = {len(newUsers)}\n{chr(10).join([repr(usr) for usr in newUsers])}")
app.stop()
