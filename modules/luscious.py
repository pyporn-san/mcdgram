import random
from os import unlink

from pyrogram import emoji, filters, types

from luscious import Luscious

from common import (NotFound, app, async_wrap, bot_telegram_id, comicArgs,
                      comicToTelegraph, inlineErrorCatching, luscious_login, luscious_password,
                      makeButtons, makeCollage, prepareComicText, sendComic,
                      sendVideo, telegraphArgs)

Lus = Luscious(luscious_login, luscious_password)


async def prepareLuscious(query, Lus):
    if(query == "random"):
        lusInput = Lus.getRandomId()
    elif(query.isnumeric()):
        lusInput = int(query)
    elif(query.lower().startswith("https://www.luscious.net") or query.lower().startswith("https://www.members.luscious.net")):
        lusInput = query
    result = await async_wrap(Lus.getAlbum)(lusInput)
    return result


async def prepareLusciousVideo(query, Lus):
    if(query == "random"):
        # lusInput = Lus.getRandomId()
        # TODO
        raise NotFound
    elif(query.isnumeric()):
        lusInput = int(query)
    elif(query.lower().startswith("https://www.luscious.net") or query.lower().startswith("https://www.members.luscious.net")):
        lusInput = query
    result = await async_wrap(Lus.getVideo)(lusInput)
    return result


async def searchLuscious(query, isVideo, Lus, page=1):
    try:
        if(isVideo):
            comicList = await async_wrap(Lus.searchVideo)(" ".join(query.split(" ")[1:]))
        else:
            comicList = await async_wrap(Lus.searchAlbum)(query)
        assert(len(comicList) > 0)
        return comicList
    except:
        raise NotFound


@app.on_message(filters.command(["luscious", f"luscious{bot_telegram_id}"]))
async def getLuscious(client, message):
    if(len(message.command) < 2):
        await message.reply_text("Usage: \
            \n1. /luscious (video) link\
            \nExamples:\
            \n/luscious https://members.luscious.net/albums/mavis-dracula_387509/\
            \n/luscious video https://members.luscious.net/videos/dropout-01_6653/\
            \n\n2. /luscious (video) id\
            \nExamples:\
            \n/luscious 387509\
            \n/luscious video 6653\
            \n\n3. /luscious (video) search query\
            \nExamples:\
            \n/luscious gravity falls\
            \n/luscious video dropout\
            \n\n4. /luscious random", disable_web_page_preview=True)
        return
    try:
        isVideo = message.command[1].lower() == "video"
        if(message.command[1+isVideo].isnumeric() or message.command[1+isVideo].lower().startswith("https://") or message.command[1+isVideo] == "random"):
            if(isVideo):
                result = await prepareLusciousVideo(message.command[2], Lus)
                videoLink = [s for s in result.contentUrls if s][0]
                await sendVideo(videoLink, result.name, result.url, message)
            else:
                result = await prepareLuscious(message.command[1], Lus)
                await sendComic(result, message)
        else:
            resultList = await searchLuscious(" ".join(message.command[1:]), isVideo, Lus)
            resultList = random.sample(
                resultList["items"], k=min(6, len(resultList["items"])))
            resultList = [Lus.getVideo(
                i) if isVideo else Lus.getAlbum(i) for i in resultList]
            (width, height) = (400, 225) if isVideo else (225, 300)

            k = [types.InlineKeyboardButton(
                result.name, callback_data=f"LUS{'VID' if isVideo else''}:{result.json['id']}") for result in resultList]
            Buttons = makeButtons(k, 2)
            Buttons.append([types.InlineKeyboardButton(
                f"Random{emoji.GAME_DIE}", callback_data=f"LUS{'VID' if isVideo else''}:RANDOM:{min(6, len(resultList))}")])
            listOfImages = [result.thumbnail for result in resultList]
            name = f"{message.from_user.id}{message.command}{message.message_id}{random.randint(1, 10)}.jpg"
            await makeCollage(width, height, listOfImages, name)
            await message.reply_photo(name, caption="Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
            unlink(name)
            return
    except NotFound:
        await message.reply_text(f"Found no items with that query")
        return
    except Exception as er:
        print(f"{er} IN Luscious {message.command}")
        return


@app.on_callback_query(filters.regex("^LUS"))
async def processLusciousCallback(client, callback_query):
    args = callback_query.data.split(":")
    try:
        if(args[1] == "RANDOM"):
            rand = random.randint(0, int(args[2]))
            chosenId = int(
                callback_query.message.reply_markup["inline_keyboard"][rand//2][rand % 2]["callback_data"].split(":")[1])
        else:
            chosenId = int(args[1])
        msg = callback_query.message.reply_to_message
        msg.command = ["/luscious", str(chosenId)]
        if(args[0] == "LUSVID"):
            msg.command.insert(1, "video")
        await callback_query.message.delete()
        await getLuscious(client, msg)
        return
    except Exception as e:
        print(e)
        await callback_query.message.reply_text("Something went wrong")


@app.on_inline_query(filters.regex(f"^{bot_telegram_id} lus .+"))
async def answerInline(client, inline_query):
    async def temp(client, inline_query):
        searchQuery = " ".join(inline_query.query.split(" ")[1:])
        if(searchQuery.isnumeric()):
            hentaiList = [await prepareLuscious(searchQuery, Lus)]
        else:
            hentaiList = (await searchLuscious(searchQuery, False, Lus))["items"]
            hentaiList = hentaiList[:5]
            hentaiList = [Lus.getAlbum(i) for i in hentaiList]
        await inline_query.answer([types.InlineQueryResultArticle(title=result.name,
                                                                input_message_content=types.InputTextMessageContent(await prepareComicText(noLink=True, **comicArgs(result, noContent=True))),
                                                                thumb_url=result.thumbnail,
                                                                reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("Instant view", url=await comicToTelegraph(**telegraphArgs(result)))]]))
                                for result in hentaiList], cache_time=15)
    await inlineErrorCatching(temp, client, inline_query)