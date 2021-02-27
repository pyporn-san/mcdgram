import asyncio
import random
import urllib
from functools import partial, wraps
from os import environ, path
from urllib.parse import urlparse

import dotenv
import rule34
from hentai import Format, Hentai, Utils
from multporn import Multporn
from multporn import Utils as MPUtils
from pybooru import Danbooru
from pyrogram import Client, emoji, filters, idle, types
from telegraph import Telegraph, upload

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

app = Client(":memory:", api_id, api_hash, bot_token=bot_token)
telegraph = Telegraph()
telegraph.create_account(author_name=telegraph_name,
                         author_url=telegraph_url, short_name=telegraph_short_name)


class notFound(Exception):
    pass


class uploadError(Exception):
    pass


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    return run


async def uploadImage(img, handler=None):
    try:
        if(not handler):
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.3'}
            req = urllib.request.Request(url=img, headers=headers)
            with await async_wrap(urllib.request.urlopen)(req) as f:
                result = await async_wrap(upload.upload_file)(f)
                return result[0]
        else:
            file = await async_wrap(handler.get)(img, stream=True)
            file = file.raw
            result = await async_wrap(upload.upload_file)(file)
            return result[0]
    except Exception as er:
        print(f"{er} on {img}")
        return img


async def uplaodToTelegraph(links, handler=None):
    tasks = [asyncio.create_task(uploadImage(link, handler)) for link in links]
    uploaded = await asyncio.gather(*tasks)
    return uploaded


async def sendComic(links, name, handler=None):
    # Uploading files to telegra.ph
    print(name, len(links))
    try:
        uploaded = await uplaodToTelegraph(links, handler)
        print(f"Uploading success for {name}")
    except Exception as er:
        print(f"Fallback on {name} becuase {er}")
        uploaded = links
    # Generating html for the post
    html = ''.join([f'<img src="{image}">' for image in uploaded])
    # Sending html to telegraph
    response = await async_wrap(telegraph.create_page)(
        name, html_content=html, author_name=telegraph_name, author_url=telegraph_url)
    return f'https://telegra.ph/{response["path"]}'


def parseComic(title, link, pages, tags=None, ongoing=None):
    post = f'[{title}]({link})\n\n'
    if(ongoing != None):
        post += f'Status: {"Ongoing" if ongoing else "Completed"}\n\n'
    if(tags):
        post += 'Tags:\n'
        for tag in tags:
            post += f'#{tag.capitalize().replace(" ","_").replace("-","_")} '
        post = post.strip()
        post += '\n\n'
    post += f'Pages: {pages}'
    return post


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

@app.on_message(filters.regex("^\/"), group=-1)
async def logger(client, message):
    await app.send_message(-1001398894102,text=f"{message.text} by {message.from_user.first_name} {message.from_user.last_name}")

@app.on_message(filters.command(["rule34", f"rule34{bot_telegram_id}"]))
async def getRule34(client, message):
    # If empty tell the usage
    if(len(message.command) == 1):
        await message.reply_text("Usage:\n/rule34 tags\nExample:\n/rule34 creampie deepthroat\n\nDifferent tags are seperated by spaces. For multiword tags use \"_\" instead of space")
        return
    r34 = rule34.Rule34(asyncio.get_event_loop())
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
        images = await r34.getImages(query)
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
            if(len(images)>10):
                raise uploadError
            for image in images:
                try:
                    if(image.file_url.split(".")[-1] in ("webm","gif")):
                        raise uploadError
                    else:
                        mediaGroup.append(types.InputMediaPhoto(image.file_url))
                except:
                    raise uploadError
            if(mediaGroup):
                try:
                    await message.reply_media_group(mediaGroup)
                    await msg.delete()
                except:
                    raise uploadError
        except uploadError:
            await msg.edit_text(msg.text+f"\nUploading to Telegraph")
            link = await sendComic([rule34.file_url for rule34 in images], verboseQuery)
            await message.reply_text(parseComic(verboseQuery, link, len(images)))
            await msg.delete()
    else:
        await msg.edit_text(f"Found no results for tags: {verboseQuery}")

@app.on_message(filters.command(["danbooru",f"danbooru{bot_telegram_id}"]))
async def getDanbooru(client, message):
    # If empty tell the usage
    if(len(message.command) == 1):
        await message.reply_text("Usage:\n/danbooru tags\nExample:\n/danbooru rating:explicit bunny_girl\n\nDifferent tags are seperated by spaces. For multiword tags use \"_\" instead of space")
        return
    danClient = Danbooru('danbooru', username=danbooru_login, api_key=danbooru_api_key)
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
            if(len(images)>10):
                raise uploadError
            mediaGroup = []
            for image in images:
                try:
                    if(image.split(".")[-1] in ("webm","gif")):
                        raise uploadError
                    else:
                        mediaGroup.append(types.InputMediaPhoto(image))
                except:
                    raise uploadError
            if(mediaGroup):
                try:
                    await message.reply_media_group(mediaGroup)
                    await msg.delete()
                except:
                    raise uploadError
        except uploadError:
            await msg.edit_text(msg.text+f"\nUploading to Telegraph")
            link = await sendComic(images, verboseQuery)
            await message.reply_text(parseComic(verboseQuery, link, len(images)))
            await msg.delete()
    else:
        await msg.edit_text(f"Found no results for tags: {verboseQuery}")

@app.on_message(filters.command(["nhentai", f"nhentai{bot_telegram_id}"]))
async def getNhentai(client, message):
    if(len(message.command) < 2):
        await message.reply_text("Usage : \n1. /nhentai id\nExample:\n/nhentai 177013\n\n2. /nhentai search query\nExample:\n/nhentai vanilla neko\n\n3. /nhentai random")
        return
    try:
        if(message.command[1].lower() == "random" and len(message.command) == 2):
            hentaiId = Utils.get_random_id()
        elif(message.command[1].isnumeric() and len(message.command) == 2):
            hentaiId = int(message.command[1])
        else:
            hentaiList = await async_wrap(Utils.search_by_query)(" ".join(message.command[1:]))
            hentaiList = random.sample(hentaiList, k=min(6, len(hentaiList)))
            k = [types.InlineKeyboardButton(hentai.title(
                Format.Pretty), callback_data=f"NHENTAI:{hentai.id}") for hentai in hentaiList]
            Buttons = makeButtons(k, [2, 2, 2])
            if(len(Buttons) == 0):
                raise notFound
            Buttons.append([types.InlineKeyboardButton(
                f"Random{emoji.GAME_DIE}", callback_data=f"NHENTAI:{min(6, len(hentaiList))}RANDOM")])
            await message.reply_text("Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
            return
        try:
            doujin = await async_wrap(Hentai)(hentaiId)
            msg = await message.reply_text(f"{doujin.title(Format.Pretty)}\n\nPages: {len(doujin.image_urls)}")
        except:
            raise notFound
    except notFound:
        await message.reply_text(f"No such hentai with that query")
        return
    # For debugging
    except Exception as er:
        print(f"{er} IN HENTAI {message.command}")
        return
    # When everything is done send the douhjin
    link = await sendComic(doujin.image_urls, doujin.title(Format.Pretty))
    tags = [tag.name for tag in doujin.tag]
    await msg.edit_text(parseComic(doujin.title(Format.Pretty), link, len(doujin.image_urls), tags=tags, ongoing="ongoing" in doujin.title(Format.English).lower()))


@app.on_message(filters.command(["multporn", f"multporn{bot_telegram_id}"]) & ~filters.edited)
async def getMultporn(client, message):
    if(len(message.command) < 2):
        await message.reply_text("Usage: \n1. multporn link\nExample:\n/multporn https://multporn.net/comics/fortunate_mix_up\n\n2. /multporn search query\nExample:\n/multporn gravity falls", disable_web_page_preview=True)
        return
    elif(message.command[1].lower().startswith("https://multporn.net") or message.command[1].lower().startswith("multporn.net")):
        comic = await async_wrap(Multporn)(message.command[1])
        msg = await message.reply_text(f"{comic.name}\n\nPages: {len(comic.contentUrls)}")
        link = await sendComic(comic.contentUrls, comic.name, handler=comic._Multporn__handler)
        await msg.edit_text(parseComic(comic.name, link, len(comic.contentUrls), tags=comic.tags, ongoing=comic.ongoing))
        return
    else:
        comicList = await async_wrap(MPUtils.Search)(" ".join(message.command[1:]))
        comicList = random.sample(comicList, k=min(6, len(comicList)))
        comicList = list(map(Multporn, comicList))
        print(comicList)
        k = [types.InlineKeyboardButton(
            comic.name, callback_data=f"MULTPORN:{comic.url.split('multporn.net')[-1]}") for comic in comicList]
        Buttons = makeButtons(k, [2, 2, 2])
        if(len(Buttons) == 0):
            raise notFound
        Buttons.append([types.InlineKeyboardButton(
            f"Random{emoji.GAME_DIE}", callback_data=f"MULTPORN:{min(6, len(comicList))}RANDOM")])
        await message.reply_text("Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
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
            msg = await callback_query.message.edit_text(f"Chosen: {chosenId}")
            doujin = Hentai(chosenId)
            msg = await msg.edit_text(f"chosen {chosenId} : {doujin.title(Format.Pretty)}")
            link = await sendComic(doujin.image_urls, doujin.title(Format.Pretty))
            tags = [tag.name for tag in doujin.tag]
            await msg.edit_text(parseComic(doujin.title(Format.Pretty), link, len(doujin.image_urls), tags=tags, ongoing="ongoing" in doujin.title(Format.English).lower()))
            return
        elif(callback_query.data.startswith("MULTPORN:")):
            if(callback_query.data[10:] == "RANDOM"):
                rand = random.randint(0, int(callback_query.data[9]))
                chosenLink = callback_query.message.reply_markup["inline_keyboard"][rand//2][rand % 2]["callback_data"][9:]
            else:
                chosenLink = callback_query.data[9:]
            chosenLink = "https://multporn.net"+chosenLink
            msg = await callback_query.message.edit_text(f"Chosen: {chosenLink}")
            comic = Multporn(chosenLink)
            msg = await msg.edit_text(f"chosen: [{comic.name}]({chosenLink})")
            link = await sendComic(comic.contentUrls, comic.name)
            await msg.edit_text(parseComic(comic.name, link, len(comic.contentUrls), tags=comic.tags, ongoing=comic.ongoing))
            return
    except ValueError:
        await callback_query.message.reply_text("Uuuuuuuuhhhh\nYou shoudnlt've seen this")

app.start()
app.send_message(owner_id, "Started")
print("Started")
idle()
app.send_message(owner_id, "Manual Stopping")
print("Manual Stopping")
app.stop()
