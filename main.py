import asyncio
import random
import urllib.request
from functools import partial, wraps
from io import BytesIO
from os import environ, listdir, unlink
from pathlib import Path
from urllib.parse import urlparse

import dotenv
import requests
import rule34
from hentai import Format, Hentai, Utils
from luscious import Luscious
from multporn import Multporn
from multporn import Utils as MPUtils
from PIL import Image
from pybooru import Danbooru
from pygelbooru import Gelbooru
from pyrogram import Client, emoji, filters, idle, types
from pyrogram.errors import QueryIdInvalid
from telegraph import Telegraph, upload, TelegraphException

import sources

dotenv.load_dotenv()
api_id = int(environ["API_ID"])
api_hash = environ["API_HASH"]
bot_token = environ["BOT_TOKEN"]
owner_id = int(environ["OWNER_ID"])
telegraph_name = environ["TELEGRAPH_NAME"]
telegraph_url = environ["TELEGRAPH_URL"]
telegraph_short_name = environ["TELEGRAPH_SHORT_NAME"]
bot_telegram_id = environ["BOT_TELEGRAM_ID"]
danbooru_login = environ["DANBOORU_LOGIN"]
danbooru_api_key = environ["DANBOORU_API_KEY"]
gelbooru_id = environ["GELBOORU_ID"]
gelbooru_api_key = environ["GELBOORU_API_KEY"]
luscious_login = environ["LUSCIOUS_LOGIN"]
luscious_password = environ["LUSCIOUS_PASSWORD"]
logo_url = environ["LOGO_URL"]

app = Client(":memory:", api_id, api_hash, bot_token=bot_token)
telegraph = Telegraph()
telegraph.create_account(author_name=telegraph_name,
                         author_url=telegraph_url, short_name=telegraph_short_name)

Lus = Luscious(luscious_login, luscious_password)
gelClient = Gelbooru(gelbooru_api_key, gelbooru_id)
danClient = Danbooru('danbooru', username=danbooru_login,
                     api_key=danbooru_api_key)
r34Client = rule34.Rule34(asyncio.get_event_loop())

width, height = 225, 300


class NotFound(Exception):
    pass


class UploadError(Exception):
    pass


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    return run

# Preparing comics/video


async def comicToTelegraph(images, title, handler=None):
    images = images[:500]

    # Generating html for the post
    html = ''.join([f'<img src="{image}">' for image in images])
    # Sending html to telegraph
    response = await async_wrap(telegraph.create_page)(
        title, html_content=html, author_name=telegraph_name, author_url=telegraph_url)
    return f'https://telegra.ph/{response["path"]}'


def parseComic(telegraphUrl=None, title=None, pages=None, tags=None, characters=None, artists=None, contentType=None, ongoing=None, isManga=None, noLink=False):
    if(noLink):
        post=f'{title}\n\n'
    else:
        post = f'[{title}]({telegraphUrl})\n\n'

    if(ongoing != None and isManga):
        post += f'Status: {"Ongoing" if ongoing else "Completed"}\n\n'
    if(tags):
        post += 'Tags:\n'
        for tag in tags:
            post += f'#{tag.title().replace(" ","_").replace("-","_")} '
        post = post.strip()
        post += '\n\n'
    if(characters):
        post += 'Characters: '
        for character in characters:
            post += f'#{character.title().replace(" ","_").replace("-","_")} '
        post = post.strip()
        post += '\n\n'
    if(artists):
        post += 'Artists: '
        for artist in artists:
            post += f'#{artist.title().replace(" ","_").replace("-","_")} '
        post = post.strip()
        post += '\n\n'
    if(contentType):
        post += f'Content Type: #{contentType}\n\n'
    post += f'Pages: {pages}'
    return post


async def sendVideo(videoUrl, name, url, message):
    msg = await message.reply_text(f"video: [{name}]({url})")
    try:
        await message.reply_video(videoUrl)
    except:
        await msg.edit_text(msg.text+"\n\nUploading manually")
        b = BytesIO(requests.get(videoUrl).content)
        b.name = name + ".mp4"
        await message.reply_video(b)
    await msg.delete()


async def sendComic(obj, message=None):
    kwargs = sources.comicArgs(obj)

    msg = await message.reply_text(f"[{kwargs['title']}]({kwargs['url']})\n\nPages: {len(kwargs['comicPages'])}")
    await message.reply_text(await prepareComicText(**kwargs))

    await msg.delete()


async def prepareComicText(comicPages=None, pages=None, title=None, tags=None, characters=None, artists=None, contentType=None, ongoing=None, isManga=None, handler=None, noLink=False, **kwargs):
    telegraphUrl = "" if noLink else await comicToTelegraph(comicPages, title, handler=handler)
    return parseComic(title=title, telegraphUrl=telegraphUrl, pages=pages, tags=tags, characters=characters, artists=artists, contentType=contentType, ongoing=ongoing, isManga=isManga, noLink=noLink)


def makeButtons(buttons, buttonTable):
    buttons = iter(buttons)
    Table = []
    try:
        for i in range(len(buttonTable)):
            Table.append([])
            for _ in range(buttonTable[i]):
                Table[i].append(next(buttons))
        return Table
    except StopIteration:
        if(Table[-1] == []):
            Table.pop()
        return Table


async def downloadImages(links):
    tasks = [asyncio.create_task(downloadFile(link)) for link in links]
    files = await asyncio.gather(*tasks)
    return files


async def downloadFile(link):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.3'}
    req = urllib.request.Request(url=link, headers=headers)
    f = await async_wrap(urllib.request.urlopen)(req)
    return f


async def makeCollage(twidth, theight, listOfImages, name):
    cols, rows = (2, (len(listOfImages)+1)//2)
    listOfImages = await downloadImages(listOfImages)
    ew, eh = round(twidth/20),  round(theight/40)
    width, height = twidth*cols+(cols-1)*ew, theight*rows+(rows-1)*eh
    new_im = Image.new('RGB', (width, height))
    ims = []
    for p in listOfImages:
        im = Image.open(p)
        im = crop_maintain_ratio(im, twidth, theight)
        ims.append(im)
    x = y = 0
    try:
        for row in range(rows):
            for col in range(cols):
                if(len(ims) % 2 == 1 and row*cols+col == len(ims)-1):
                    new_im.paste(ims[row*cols+col], (x+twidth//2, y))
                else:
                    new_im.paste(ims[row*cols+col], (x, y))
                x += twidth+ew
            y += theight + eh
            x = 0
    except:
        pass
    new_im.save(name, quality=95)


def crop_maintain_ratio(img, w, h):
    OW, OH = img.size
    if(OW/OH > w/h):
        NW = OH*w/h
        img = img.crop(((OW-NW)//2, 0, (OW+NW)//2, OH))
    else:
        NH = OW*h/w
        img = img.crop((0, (OH-NH)//2, OW, (OH+NH)//2))
    img.thumbnail([w, h])
    img = img.resize([w, h])
    return img


@app.on_message(filters.regex(r"^\/"), group=-1)
async def logger(client, message):
    if(message.from_user.id != 80244858):
        await app.send_message(-1001398894102, text=f"{message.from_user.first_name} {message.from_user.last_name if message.from_user.last_name else ''}: {message.text}")


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


@app.on_message(filters.command(["rule34", f"rule34{bot_telegram_id}"]))
async def getRule34(client, message):
    # If empty tell the usage
    if(len(message.command) == 1):
        await message.reply_text("Usage:\
            \n/rule34 tags\
            \nExample:\
            \n/rule34 creampie deepthroat\
            \n\nDifferent tags are seperated by spaces. For multiword tags use \"_\" instead of space")
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


@app.on_message(filters.command(["danbooru", f"danbooru{bot_telegram_id}"]))
async def getDanbooru(client, message):
    # If empty tell the usage
    if(len(message.command) == 1):
        await message.reply_text("Usage:\
            \n/danbooru tags\
            \nExample:\
            \n/danbooru rating:explicit bunny_girl\
            \n\nDifferent tags are seperated by spaces. For multiword tags use \"_\" instead of space")
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
        posts = danClient.post_list(tags=query, random=True, limit=200)
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
            images = []
            for post in posts:
                try:
                    fileurl = post['file_url']
                except:
                    fileurl = 'https://danbooru.donmai.us' + post['source']
                images.append(fileurl)
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


@app.on_message(filters.command(["gelbooru", f"gelbooru{bot_telegram_id}"]))
async def getGelbooru(client, message):
    # If empty tell the usage
    if(len(message.command) == 1):
        await message.reply_text("Usage:\
            \n/gelbooru tags\
            \nExample:\
            \n/gelbooru rating:explicit bunny_girl\
            \n\nDifferent tags are seperated by spaces. For multiword tags use \"_\" instead of space")
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
            doujin = await sources.prepareNhentai(message.command[1])
            await sendComic(doujin, message)
        else:
            hentaiList = await sources.searchNhentai(" ".join(message.command[1:]))
            hentaiList = hentaiList[:6]
            k = [types.InlineKeyboardButton(hentai.title(
                Format.Pretty), callback_data=f"NHENTAI:{hentai.id}") for hentai in hentaiList]
            Buttons = makeButtons(k, [2, 2, 2])
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
            comic = await sources.prepareMultporn(message.command[1])
            if(comic.contentType == "video"):
                await sendVideo(comic.contentUrls[0], comic.name, comic.url, message)
            else:
                await sendComic(comic, message)
        else:
            comicList = await sources.searchMultporn(" ".join(message.command[1:]))
            comicList = comicList[:6]
            k = [types.InlineKeyboardButton(
                comic["name"], callback_data=f"MULTPORN:{comic['link'].split('multporn.net')[-1]}") for comic in comicList]
            Buttons = makeButtons(k, [2, 2, 2])
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
            \n\n3. /lusvious (video) search query\
            \nExamples:\
            \n/luscious gravity falls\
            \n/luscious video dropout\
            \n\n4. /luscious random", disable_web_page_preview=True)
        return
    try:
        isVideo = message.command[1].lower() == "video"
        if(message.command[1+isVideo].isnumeric() or message.command[1+isVideo].lower().startswith("https://") or message.command[1+isVideo] == "random"):
            if(isVideo):
                result = await sources.prepareLusciousVideo(message.command[2], Lus)
                videoLink = [s for s in result.contentUrls if s][0]
                await sendVideo(videoLink, result.name, result.url, message)
            else:
                result = await sources.prepareLuscious(message.command[1], Lus)
                await sendComic(result, message)
        else:
            resultList = await sources.searchLuscious(" ".join(message.command[1:]), isVideo, Lus)
            resultList = random.sample(
                resultList["items"], k=min(6, len(resultList["items"])))
            resultList = [Lus.getVideo(
                i) if isVideo else Lus.getAlbum(i) for i in resultList]
            (width, height) = (400, 225) if isVideo else (225, 300)

            k = [types.InlineKeyboardButton(
                result.name, callback_data=f"LUS{'VID' if isVideo else''}:{result.json['id']}") for result in resultList]
            Buttons = makeButtons(k, [2, 2, 2])
            Buttons.append([types.InlineKeyboardButton(
                f"Random{emoji.GAME_DIE}", callback_data=f"LUS{'VID' if isVideo else''}:{min(6, len(resultList))}RANDOM")])
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


@app.on_message(filters.private & filters.regex("^[0-9]*$") & ~filters.edited)
async def nhentaiNoCommand(client, message):
    message.command = ["/nhentai", message.matches[0].string]
    await getNhentai(client, message)


@app.on_callback_query()
async def processCallback(client, callback_query):
    try:
        if(callback_query.data.startswith("NHENTAI:")):
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
        elif(callback_query.data.startswith("MULTPORN:")):
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
        elif(callback_query.data.startswith("LUS:")):
            if(callback_query.data[5:] == "RANDOM"):
                rand = random.randint(0, int(callback_query.data[4]))
                chosenId = int(
                    callback_query.message.reply_markup["inline_keyboard"][rand//2][rand % 2]["callback_data"][8:])
            else:
                chosenId = int(callback_query.data[4:])
            msg = callback_query.message.reply_to_message
            msg.command = ["/luscious", str(chosenId)]
            await callback_query.message.delete()
            await getLuscious(client, msg)
            return
        elif(callback_query.data.startswith("LUSVID:")):
            if(callback_query.data[8:] == "RANDOM"):
                rand = random.randint(0, int(callback_query.data[7]))
                chosenId = int(
                    callback_query.message.reply_markup["inline_keyboard"][rand//2][rand % 2]["callback_data"][8:])
            else:
                chosenId = int(callback_query.data[7:])
            msg = callback_query.message.reply_to_message
            msg.command = ["/luscious", "video", str(chosenId)]
            await callback_query.message.delete()
            await getLuscious(client, msg)
            return
    except Exception as e:
        print(e)
        # await callback_query.message.reply_text("Uuuuuuuuhhhh\nYou shouldnt've seen this")


@app.on_inline_query()
async def answerInline(client, inline_query):
    if(inline_query.from_user.id != 80244858):
        await app.send_message(-1001398894102, text=f"{inline_query.from_user.first_name} {inline_query.from_user.last_name if inline_query .from_user.last_name else ''}: {bot_telegram_id} {' '.join(inline_query.query.split(' ')[1:])}")

    ratings = {"s": "Safe", "q": "Questionable", "e": "Explicit"}
    searchQuery = " ".join(inline_query.query.split(" ")[1:])
    offset = int(inline_query.offset) if inline_query.offset else 0

    print(offset, searchQuery)
    try:
        if(inline_query.query.startswith("gel") and searchQuery):
            try:
                images = (await gelClient.search_posts(tags=searchQuery.split(" "), page=offset//2))
                images = images[:50] if not offset % 2 else images[50:]
                await inline_query.answer([types.InlineQueryResultPhoto(str(image), reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton(ratings[image.rating], url=f"https://gelbooru.com/index.php?page=post&s=view&id={image.id}")]]), input_message_content=types.InputTextMessageContent("Video\nClick on link below to view") if ("video" in image.tags or "webm" in image.tags) else None) for image in images], is_gallery=True, next_offset=str(offset+1) if images else "", cache_time=15)
            except:
                await inline_query.answer([])
        elif(inline_query.query.startswith("dan") and searchQuery):
            try:
                images = (await async_wrap(danClient.post_list)(tags=searchQuery, page=offset*2)) + (await async_wrap(danClient.post_list)(tags=searchQuery, page=offset*2+1))
                images = [
                    image for image in images if "file_url" in image.keys()]
                await inline_query.answer([types.InlineQueryResultPhoto(image["file_url"], reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton(ratings[image["rating"]], url=f"https://danbooru.donmai.us/posts/{image['id']}")]]), input_message_content=types.InputTextMessageContent("Video\nClick on link below to view") if ("video" in image["tag_string"] or "webm" in image["tag_string"]) else None) for image in images], is_gallery=True, next_offset=str(offset+1) if images else "", cache_time=15)
            except:
                await inline_query.answer([])
        elif(inline_query.query.startswith("rul") and searchQuery):
            try:
                images = await r34Client.getImages(searchQuery, singlePage=True,  OverridePID=offset//2)
                images = images[:50] if not offset % 2 else images[50:]
                await inline_query.answer([types.InlineQueryResultPhoto(image.file_url, reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton(ratings[image.rating], url=f"https://rule34.xxx/index.php?page=post&s=view&id={image.id}")]]), input_message_content=types.InputTextMessageContent("Video\nClick on link below to view") if ("video" in image.tags or "webm" in image.tags) else None) for image in images], is_gallery=True, next_offset=str(offset+1) if images else "", cache_time=15)
            except:
                await inline_query.answer([])

        elif(inline_query.query.startswith("nhe") and searchQuery):
            if(searchQuery.isnumeric()):
                hentaiList = [await sources.prepareNhentai(searchQuery)]
            else:
                hentaiList = await sources.searchNhentai(searchQuery)
                hentaiList = hentaiList[:5]
            await inline_query.answer([types.InlineQueryResultArticle(title=h.title(Format.Pretty),
                                                                      input_message_content=types.InputTextMessageContent(await prepareComicText(noLink=True, **sources.comicArgs(h, noContent=True))),
                                                                      thumb_url=h.thumbnail,
                                                                      reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("Instant view", url=await comicToTelegraph(**sources.telegraphArgs(h)))]]))
                                       for h in hentaiList], cache_time=15)
        elif(inline_query.query.startswith("lus") and searchQuery):
            hentaiList = (await sources.searchLuscious(searchQuery, False, Lus))["items"]
            hentaiList = hentaiList[:2]
            hentaiList = [Lus.getAlbum(i) for i in hentaiList]
            await inline_query.answer([types.InlineQueryResultArticle(title=result.name,
                                                                      input_message_content=types.InputTextMessageContent(await prepareComicText(noLink=True, **sources.comicArgs(result, noContent=True))),
                                                                      thumb_url=result.thumbnail,
                                                                      reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("Instant view", url=await comicToTelegraph(**sources.telegraphArgs(result)))]]))
                                       for result in hentaiList], cache_time=15)
        else:
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
    except TelegraphException as e:
        x = int(e.args[0].split("_")[-1])
        errorMessage = f"please wait {x} second{'s' if x>1 else''} before trying again"
        await inline_query.answer([types.InlineQueryResultArticle(title="Please wait", input_message_content=types.InputTextMessageContent(errorMessage), description=errorMessage)], cache_time=x+1)
    except QueryIdInvalid:
        pass

app.start()
app.send_message(owner_id, "Started")
print("Started")
idle()
app.send_message(owner_id, "Manual Stopping")
print("Manual Stopping")
app.stop()
