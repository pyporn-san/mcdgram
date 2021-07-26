
import random

from pygelbooru import Gelbooru
from pyrogram import filters, types

from common import (UploadError, app, bot_telegram_id, comicToTelegraph,
                      gelbooru_api_key, gelbooru_id, inlineErrorCatching, parseComic)

gelClient = Gelbooru(gelbooru_api_key, gelbooru_id)


@app.on_message(filters.command(["gelbooru", f"gelbooru{bot_telegram_id}"]))
async def getGelbooru(client, message):
    # If empty tell the usage
    if(len(message.command) == 1):
        await message.reply_text("Usage:\
            \n/gelbooru tags\
            \nExample:\
            \n/gelbooru rating:explicit bunny_girl\
            \n\n**Different tags are seperated by spaces. For multiword tags use \"_\" instead of space**")
        return
    # Number of things to return
    if(message.command[1].isnumeric()):
        limit = int(message.command[1])
        firstIsNumber = True
    else:
        limit = 1
        firstIsNumber = False
    # Tell the user of success
    query = " ".join(message.command[1+firstIsNumber:])
    verboseQuery = query.replace(" ", ", ").replace("_", " ")
    msg = await message.reply_text(f"Searching for {limit} result{'s' if limit>1 else ''} with tags: {verboseQuery}")
    try:
        posts = (await gelClient.search_posts(tags=query.split(" ")))
        if(len(posts) >= limit):
            msg = await msg.edit_text(f"Found {limit} result{'s' if limit>1 else ''}. Sending")
        else:
            msg = await msg.edit_text(f"Found only {len(posts)} result{'s' if len(posts)>1 else ''}. Sending")
        mediaGroup = []
    except (KeyError, TypeError):
        posts = []
    if(posts):
        try:
            posts = random.sample(posts, k=min(len(posts), limit))
            images = [str(post) for post in posts]
            if(len(images) > 10):
                raise UploadError
            mediaGroup = []
            for image in images:
                try:
                    if(image.split(".")[-1] in ("webm", "gif")):
                        raise UploadError
                    else:
                        mediaGroup.append(types.InputMediaPhoto(image))
                except:
                    raise UploadError
            if(mediaGroup):
                try:
                    await message.reply_media_group(mediaGroup)
                    await msg.delete()
                except:
                    raise UploadError
        except UploadError:
            await msg.edit_text(msg.text+f"\nUploading to Telegraph")
            link = await comicToTelegraph(images, verboseQuery)
            await message.reply_text(parseComic(verboseQuery, link, len(images)))
            await msg.delete()
    else:
        await msg.edit_text(f"Found no results for tags: {verboseQuery}")


@app.on_inline_query(filters.regex(f"^gel .+"))
async def answerInline(client, inline_query):
    async def temp(client, inline_query):
        ratings = {"s": "Safe", "q": "Questionable", "e": "Explicit"}
        searchQuery = " ".join(inline_query.query.split(" ")[1:])
        offset = int(inline_query.offset) if inline_query.offset else 0
        try:
            images = (await gelClient.search_posts(tags=searchQuery.split(" "), page=offset//2))
            images = images[:50] if not offset % 2 else images[50:]
            await inline_query.answer([types.InlineQueryResultPhoto(str(image), reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton(ratings[image.rating], url=f"https://gelbooru.com/index.php?page=post&s=view&id={image.id}")]]), input_message_content=types.InputTextMessageContent("Video\nClick on link below to view") if ("video" in image.tags or "webm" in image.tags) else None) for image in images], is_gallery=True, next_offset=str(offset+1) if images else "", cache_time=15)
        except:
            await inline_query.answer([])
    await inlineErrorCatching(temp, client, inline_query)