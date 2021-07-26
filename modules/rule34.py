import asyncio
import random

from pyrogram import filters, types

from rule34 import Rule34

from common import (UploadError, app, bot_telegram_id, comicToTelegraph, inlineErrorCatching,
                      parseComic)

r34Client = Rule34(asyncio.get_event_loop())


@app.on_message(filters.command(["rule34", f"rule34{bot_telegram_id}"]))
async def getRule34(client, message):
    # If empty tell the usage
    if(len(message.command) == 1):
        await message.reply_text("Usage:\
            \n/rule34 tags\
            \nExample:\
            \n/rule34 creampie deepthroat\
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
        images = await r34Client.getImages(query)
        if(len(images) >= limit):
            msg = await msg.edit_text(f"Found {limit} result{'s' if limit>1 else ''}. Sending")
        else:
            msg = await msg.edit_text(f"Found only {len(images)} result{'s' if len(images)>1 else ''}. Sending")
        mediaGroup = []
    except (KeyError, TypeError):
        images = []
    if(images):
        try:
            images = random.sample(images, k=min(len(images), limit))
            if(len(images) > 10):
                raise UploadError
            for image in images:
                try:
                    if(image.file_url.split(".")[-1] in ("webm", "gif")):
                        raise UploadError
                    else:
                        mediaGroup.append(
                            types.InputMediaPhoto(image.file_url))
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
            link = await comicToTelegraph([rule34.file_url for rule34 in images], verboseQuery)
            await message.reply_text(parseComic(verboseQuery, link, len(images)))
            await msg.delete()
    else:
        await msg.edit_text(f"Found no results for tags: {verboseQuery}")


@app.on_inline_query(filters.regex(f"^rul .+"))
async def answerInline(client, inline_query):
    async def temp(client, inline_query):
        ratings = {"s": "Safe", "q": "Questionable", "e": "Explicit"}
        searchQuery = " ".join(inline_query.query.split(" ")[1:])
        offset = int(inline_query.offset) if inline_query.offset else 0
        images = await r34Client.getImages(searchQuery, singlePage=True,  OverridePID=offset//2)
        images = images[:50] if not offset % 2 else images[50:]
        await inline_query.answer([types.InlineQueryResultPhoto(image.file_url, reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton(ratings[image.rating], url=f"https://rule34.xxx/index.php?page=post&s=view&id={image.id}")]]), input_message_content=types.InputTextMessageContent("Video\nClick on link below to view") if ("video" in image.tags or "webm" in image.tags) else None) for image in images], is_gallery=True, next_offset=str(offset+1) if images else "", cache_time=15)
    await inlineErrorCatching(temp, client, inline_query)