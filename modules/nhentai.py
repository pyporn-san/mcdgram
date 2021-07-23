import random
from os import unlink

from hentai import Format, Hentai, Utils
from pyrogram import emoji, filters, types

from common import (NotFound, app, async_wrap, bot_telegram_id, comicArgs,
                      comicToTelegraph, inlineErrorCatching, makeButtons, makeCollage,
                      prepareComicText, sendComic, telegraphArgs)

width, height = 225, 300

print("HI")
async def prepareNhentai(query):
    if(query.lower() == "random"):
        hentaiId = Utils.get_random_id()
    elif(query.isnumeric()):
        hentaiId = int(query)
    try:
        doujin = await async_wrap(Hentai)(hentaiId)
    except Exception as er:
        print(f"{er} IN HENTAI {query}")
        return
    return doujin


async def searchNhentai(query, page=1):
    try:
        hentaiList = await async_wrap(Utils.search_by_query)(query, page=page)
        assert(len(hentaiList) > 0)
        return hentaiList
    except:
        raise NotFound


@app.on_message(filters.command(["nhentai", f"nhentai{bot_telegram_id}"]))
async def getNhentai(client, message):
    if(len(message.command) < 2):
        await message.reply_text("Usage : \
            \n1. /nhentai id\
            \nExample:\
            \n/nhentai 177013\
            \n\n2. /nhentai search query\
            \nExample:\
            \n/nhentai vanilla neko\
            \n\n3. /nhentai random\
            \n\n4. Send the nhentai id without any command\
            \nExample:\
            \n177013")
        return
    try:
        if(len(message.command) == 2 and (message.command[1] == "random" or message.command[1].isnumeric())):
            doujin = await prepareNhentai(message.command[1])
            await sendComic(doujin, message)
        else:
            hentaiList = await searchNhentai(" ".join(message.command[1:]))
            hentaiList = hentaiList[:6]
            k = [types.InlineKeyboardButton(hentai.title(
                Format.Pretty), callback_data=f"NHENTAI:{hentai.id}") for hentai in hentaiList]
            Buttons = makeButtons(k, 2)
            Buttons.append([types.InlineKeyboardButton(
                f"Random{emoji.GAME_DIE}", callback_data=f"NHENTAI:{min(6, len(hentaiList))}RANDOM")])
            listOfImages = [hentai.thumbnail for hentai in hentaiList]
            name = f"{message.from_user.id}{message.command}{message.message_id}{random.randint(1, 10)}.jpg"
            await makeCollage(width, height, listOfImages, name)
            await message.reply_photo(name, caption="Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
            unlink(name)
            return
    except NotFound:
        await message.reply_text(f"Found no items with that query")
        return
    except Exception as er:
        print(f"{er} IN HENTAI {message.command}")
        return


@app.on_message(filters.private & filters.regex("^[0-9]*$") & ~filters.edited)
async def nhentaiNoCommand(client, message):
    message.command = ["/nhentai", message.matches[0].string]
    await getNhentai(client, message)


@app.on_callback_query(filters.regex("^NHE"))
async def processNhentaiCallback(client, callback_query):
    try:
        if(callback_query.data[9:] == "RANDOM"):
            rand = random.randint(0, int(callback_query.data[8]))
            chosenId = int(
                callback_query.message.reply_markup["inline_keyboard"][rand//2][rand % 2]["callback_data"][8:])
        else:
            chosenId = int(callback_query.data[8:])
        msg = callback_query.message.reply_to_message
        msg.command = ["/nhentai", str(chosenId)]
        await callback_query.message.delete()
        await getNhentai(client, msg)
        return
    except Exception as e:
        print(e)
        await callback_query.message.reply_text("Something went wrong")


@app.on_inline_query(filters.regex(f"^{bot_telegram_id} nhe .+"))
async def answerMultpornInline(client, inline_query):
    async def temp(client, inline_query):
        searchQuery = " ".join(inline_query.query.split(" ")[1:])
        if(searchQuery.isnumeric()):
            hentaiList = [await prepareNhentai(searchQuery)]
        else:
            hentaiList = await searchNhentai(searchQuery)
            hentaiList = hentaiList[:5]
        await inline_query.answer([types.InlineQueryResultArticle(title=h.title(Format.Pretty),
                                                                    input_message_content=types.InputTextMessageContent(await prepareComicText(noLink=True, **comicArgs(h, noContent=True))),
                                                                    thumb_url=h.thumbnail,
                                                                    reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("Instant view", url=await comicToTelegraph(**telegraphArgs(h)))]]))
                                    for h in hentaiList], cache_time=15)
    await inlineErrorCatching(temp, client, inline_query)