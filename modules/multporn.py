import random
from os import unlink

from pyrogram import emoji, filters, types

from multporn import Multporn
from multporn import Utils as MPUtils

from common import (NotFound, app, async_wrap, bot_telegram_id, makeButtons,
                      makeCollage, sendComic, sendVideo)

width, height = 225, 300


async def prepareMultporn(query):
    comic = await async_wrap(Multporn)(query)
    return comic


async def searchMultporn(query, page=1):
    try:
        comicList = await async_wrap(MPUtils.Search)(query, page=page)
        assert(len(comicList) > 0)
        return comicList
    except:
        raise NotFound


@app.on_message(filters.command(["multporn", f"multporn{bot_telegram_id}"]))
async def getMultporn(client, message):
    if(len(message.command) < 2):
        await message.reply_text("Usage: \
            \n1. /multporn link\
            \nExample:\
            \n/multporn https://multporn.net/comics/fortunate_mix_up\
            \n\n2. /multporn search query\
            \nExample:\
            \n/multporn gravity falls", disable_web_page_preview=True)
        return
    try:
        if(message.command[1].lower().startswith("https://multporn.net")):
            comic = await prepareMultporn(message.command[1])
            if(comic.contentType == "video"):
                await sendVideo(comic.contentUrls[0], comic.name, comic.url, message)
            else:
                await sendComic(comic, message)
        else:
            comicList = await searchMultporn(" ".join(message.command[1:]))
            comicList = comicList[:6]
            k = [types.InlineKeyboardButton(
                comic["name"], callback_data=f"MULTPORN:{comic['link'].split('multporn.net')[-1]}") for comic in comicList]
            Buttons = makeButtons(k, 2)
            Buttons.append([types.InlineKeyboardButton(
                f"Random{emoji.GAME_DIE}", callback_data=f"MULTPORN:{min(6, len(comicList))}RANDOM")])
            try:
                listOfImages = [comic["thumb"] for comic in comicList]
                name = f"{message.from_user.id}{message.command}{message.message_id}{random.randint(1, 10)}.jpg"
                await makeCollage(width, height, listOfImages, name)
                await message.reply_photo(name, caption="Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
                unlink(name)
            except Exception as e:
                print(e)
                await message.reply_text("Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
            return
    except NotFound:
        await message.reply_text(f"Found no items with that query")
        return
    except Exception as er:
        print(f"{er} IN MULTPORN {message.command}")
        return


@app.on_callback_query(filters.regex("^MUL"))
async def processMultpornCallback(client, callback_query):
    try:
        if(callback_query.data[10:] == "RANDOM"):
            rand = random.randint(0, int(callback_query.data[9]))
            chosenLink = callback_query.message.reply_markup["inline_keyboard"][rand //
                                                                                2][rand % 2]["callback_data"][9:]
        else:
            chosenLink = callback_query.data[9:]
        chosenLink = "https://multporn.net"+chosenLink
        msg = callback_query.message.reply_to_message
        msg.command = ["/multporn", chosenLink]
        await callback_query.message.delete()
        await getMultporn(client, msg)
        return
    except Exception as e:
        print(e)
        await callback_query.message.reply_text("Something went wrong")
