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
gelbooru_id = environ["GELBOORU_ID"]
gelbooru_api_key = environ["GELBOORU_API_KEY"]
luscious_login = environ["LUSCIOUS_LOGIN"]
luscious_password = environ["LUSCIOUS_PASSWORD"]

app = Client(":memory:", api_id, api_hash, bot_token=bot_token)
telegraph = Telegraph()
telegraph.create_account(author_name=telegraph_name,
                         author_url=telegraph_url, short_name=telegraph_short_name)

Lus = Luscious(luscious_login, luscious_password)
width, height = 225, 300


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


def parseComic(title, link, pages, tags=None, characters=None, artists=None, contentType=None, ongoing=None, isManga=None):
    post = f'[{title}]({link})\n\n'
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
    tasks = [asyncio.create_task(downloadImage(link)) for link in links]
    files = await asyncio.gather(*tasks)
    return files


async def downloadImage(link):
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
        await app.send_message(-1001398894102, text=f"{message.text} by {message.from_user.first_name} {message.from_user.last_name}")


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
            if(len(images) > 10):
                raise uploadError
            for image in images:
                try:
                    if(image.file_url.split(".")[-1] in ("webm", "gif")):
                        raise uploadError
                    else:
                        mediaGroup.append(
                            types.InputMediaPhoto(image.file_url))
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
    danClient = Danbooru('danbooru', username=danbooru_login,
                         api_key=danbooru_api_key)
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
                raise uploadError
            mediaGroup = []
            for image in images:
                try:
                    if(image.split(".")[-1] in ("webm", "gif")):
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
    gelClient = Gelbooru(gelbooru_api_key, gelbooru_id)
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
                raise uploadError
            mediaGroup = []
            for image in images:
                try:
                    if(image.split(".")[-1] in ("webm", "gif")):
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
            listOfImages = [hentai.thumbnail for hentai in hentaiList]
            name = f"{message.from_user.id}{message.command}{message.message_id}{random.randint(1, 10)}.jpg"
            await makeCollage(width, height, listOfImages, name)
            await message.reply_photo(name, caption="Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
            unlink(name)
            return
        try:
            doujin = await async_wrap(Hentai)(hentaiId)
            msg = await message.reply_text(f"{doujin.title(Format.Pretty)}\n\nPages: {len(doujin.image_urls)}")
        except:
            raise notFound
    except notFound:
        await message.reply_text(f"Found no items with that query")
        return
    # For debugging
    except Exception as er:
        print(f"{er} IN HENTAI {message.command}")
        return
    # When everything is done send the douhjin
    link = await sendComic(doujin.image_urls, doujin.title(Format.Pretty))
    tags = [tag.name for tag in doujin.tag]
    await msg.edit_text(parseComic(doujin.title(Format.Pretty), link, len(doujin.image_urls), tags=tags, ongoing="ongoing" in doujin.title(Format.English).lower()))


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
    elif(message.command[1].lower().startswith("https://multporn.net")):
        try:
            comic = await async_wrap(Multporn)(message.command[1])
        except:
            await message.reply_text("Invalid url")
            return
        if(comic.contentType == "video"):
            msg = await message.reply_text(f"video: [{comic.name}]({comic.url})")
            try:
                await message.reply_video(comic.contentUrls[0])
            except:
                await msg.edit_text(msg.text+"\n\nUploading manually")
                fpath = await async_wrap(comic.downloadContent)(root=Path(f"{message.message_id}{random.randint(1,10)}"), printProgress=False)
                await message.reply_video(fpath[0])
                fpath[0].unlink()
        else:
            msg = await message.reply_text(f"[{comic.name}]({comic.url})\n\nPages: {len(comic.contentUrls)}")
            link = await sendComic(comic.contentUrls, comic.name, handler=comic._Multporn__handler)
            await message.reply_text(parseComic(comic.name, link, len(comic.contentUrls), tags=comic.tags, ongoing=comic.ongoing))
        await msg.delete()
        return
    else:
        comicList = await async_wrap(MPUtils.Search)(" ".join(message.command[1:]))
        comicList = comicList[:6]
        k = [types.InlineKeyboardButton(
            comic["name"], callback_data=f"MULTPORN:{comic['link'].split('multporn.net')[-1]}") for comic in comicList]
        Buttons = makeButtons(k, [2, 2, 2])
        if(len(Buttons) == 0):
            await message.reply_text("Found no items with that query")
            return
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
        if(message.command[1].lower() == "random" and len(message.command) == 2+isVideo):
            lusInput = Lus.getRandomId()
        elif(message.command[1+isVideo].isnumeric() and len(message.command) == 2+isVideo):
            lusInput = int(message.command[1+isVideo])
        elif(message.command[1+isVideo].lower().startswith("https://www.luscious.net") or message.command[1+isVideo].lower().startswith("https://www.members.luscious.net")):
            lusInput = message.command[1+isVideo]
        else:
            if(isVideo):
                resultList = await async_wrap(Lus.searchVideo)(" ".join(message.command[2:]))
                resultList = random.sample(
                    resultList["items"], k=min(6, len(resultList["items"])))
                resultList = [Lus.getVideo(i) for i in resultList]
                width, height = 400, 225
            else:
                resultList = await async_wrap(Lus.searchAlbum)(" ".join(message.command[1:]))
                resultList = random.sample(
                    resultList["items"], k=min(6, len(resultList["items"])))
                resultList = [Lus.getAlbum(i) for i in resultList]
                width, height = 225, 300

            k = [types.InlineKeyboardButton(
                result.name, callback_data=f"LUS{'VID' if isVideo else''}:{result.json['id']}") for result in resultList]
            Buttons = makeButtons(k, [2, 2, 2])
            if(len(Buttons) == 0):
                raise notFound
            Buttons.append([types.InlineKeyboardButton(
                f"Random{emoji.GAME_DIE}", callback_data=f"LUS{'VID' if isVideo else''}:{min(6, len(resultList))}RANDOM")])
            listOfImages = [result.thumbnail for result in resultList]
            name = f"{message.from_user.id}{message.command}{message.message_id}{random.randint(1, 10)}.jpg"
            await makeCollage(width, height, listOfImages, name)
            await message.reply_photo(name, caption="Choose one", reply_markup=types.InlineKeyboardMarkup(Buttons), quote=True)
            unlink(name)
            return
        try:
            if(isVideo):
                result = await async_wrap(Lus.getVideo)(lusInput)
                msg = await message.reply_text(f"video: [{result.name}]({result.url})")
            else:
                result = await async_wrap(Lus.getAlbum)(lusInput)
                msg = await message.reply_text(f"{result.name}\n\nPages: {len(result.contentUrls)}")
        except:
            raise notFound
    except notFound:
        await message.reply_text(f"Found no items with that query")
        return
    # For debugging
    except Exception as er:
        print(f"{er} IN Luscious {message.command}")
        return
    # When everything is done send the results
    if(isVideo):
        try:
            await message.reply_video(result.contentUrls[0])
        except:
            await msg.edit_text(msg.text+"\n\nUploading manually")
            for i in result.contentUrls:
                if(i):
                    b = BytesIO(requests.get(i).content)
                    b.name = "TEMP.mp4"
                    await message.reply_video(b)
                    break

    else:
        link = await sendComic(result.contentUrls, result.name)
        tags = [tag.name for tag in result.tags if not tag.category]
        await message.reply_text(parseComic(result.name, link, len(result.contentUrls), tags=tags, characters=result.characters, artists=result.artists, contentType=result.contentType, ongoing=result.ongoing, isManga=result.isManga))
    await msg.delete()


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

app.start()
app.send_message(owner_id, "Started")
print("Started")
idle()
app.send_message(owner_id, "Manual Stopping")
print("Manual Stopping")
app.stop()
