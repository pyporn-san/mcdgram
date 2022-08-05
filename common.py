import asyncio
import urllib.request
from functools import partial, wraps
from io import BytesIO
from itertools import repeat
from os import environ

import dotenv
import requests
from hentai import Format, Hentai
from luscious import Album
from multporn import Multporn
from PIL import Image
from pyrogram import Client, types
from pyrogram.errors import QueryIdInvalid
from telegraph import Telegraph, TelegraphException

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

konachan_login = environ["KONACHAN_LOGIN"]
konachan_password = environ["KONACHAN_PASSWORD"]

yandere_login = environ["YANDERE_LOGIN"]
yandere_password = environ["YANDERE_PASSWORD"]

luscious_login = environ["LUSCIOUS_LOGIN"]
luscious_password = environ["LUSCIOUS_PASSWORD"]

logo_url = environ["LOGO_URL"]

app = Client("MCDGram", api_id, api_hash, bot_token=bot_token, in_memory=True)
telegraph = Telegraph()
telegraph.create_account(author_name=telegraph_name,
                         author_url=telegraph_url, short_name=telegraph_short_name)


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


async def inlineErrorCatching(func, client, inline_query):
    try:
        value = await func(client, inline_query)
        return value
    except TelegraphException as e:
        x = int(e.args[0].split("_")[-1])
        errorMessage = f"please wait {x} second{'s' if x>1 else''} before trying again"
        await inline_query.answer([types.InlineQueryResultArticle(title="Please wait", input_message_content=types.InputTextMessageContent(errorMessage), description=errorMessage)], cache_time=x+1)
    except QueryIdInvalid:
        pass

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
        post = f'{title}\n\n'
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


async def sendComic(obj, message=None,reply_markup=None):
    kwargs = comicArgs(obj)

    msg = await message.reply_text(f"[{kwargs['title']}]({kwargs['url']})\n\nPages: {len(kwargs['comicPages'])}")
    await message.reply_text(await prepareComicText(**kwargs), reply_markup=reply_markup)

    await msg.delete()


async def prepareComicText(comicPages=None, pages=None, title=None, tags=None, characters=None, artists=None, contentType=None, ongoing=None, isManga=None, handler=None, noLink=False, **kwargs):
    telegraphUrl = "" if noLink else await comicToTelegraph(comicPages, title, handler=handler)
    return parseComic(title=title, telegraphUrl=telegraphUrl, pages=pages, tags=tags, characters=characters, artists=artists, contentType=contentType, ongoing=ongoing, isManga=isManga, noLink=noLink)


def makeButtons(buttons, buttonTable):
    if(isinstance(buttonTable, int)):
        buttonTable = list(repeat(buttonTable, len(buttons)//buttonTable+1))
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

######


def comicArgs(obj, noContent=False):
    if(isinstance(obj, Hentai)):
        return {"comicPages": [] if noContent else obj.image_urls, "pages": obj.num_pages, "title": obj.title(Format.Pretty), "url": obj.url, "tags": [tag.name for tag in obj.tag], "ongoing": "ongoing" in obj.title(Format.Pretty).lower(), "isManga": True, "handler": None}
    elif(isinstance(obj, Multporn)):
        return {"comicPages": [] if noContent else obj.contentUrls, "pages": obj.pageCount, "title": obj.name, "url": obj.url, "tags": obj.tags, "ongoing": obj.ongoing, "isManga": True, "handler": obj.handler}
    elif(isinstance(obj, Album)):
        return {"comicPages": [] if noContent else obj.contentUrls, "pages": obj.pictureCount + obj.animatedCount, "title":  obj.name, "url":  obj.url, "tags": [tag.name for tag in obj.tags if not tag.category], "characters": obj.characters, "artists": obj.artists, "contentType": obj.contentType, "ongoing": obj.ongoing, "isManga": obj.isManga, "handler": obj.handler}


def telegraphArgs(obj):
    if(isinstance(obj, Hentai)):
        return {"images": obj.image_urls, "title": obj.title(Format.Pretty), "handler": None}
    elif(isinstance(obj, Multporn)):
        return {"images": obj.contentUrls, "title": obj.title, "handler": obj.handler}
    elif(isinstance(obj, Album)):
        return {"images": obj.contentUrls, "title": obj.name, "handler": obj.handler}
