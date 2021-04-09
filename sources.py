from functools import partial, wraps
import asyncio

import requests
import rule34
from hentai import Format, Hentai, Utils
from luscious import Luscious
from multporn import Multporn
from multporn import Utils as MPUtils
from PIL import Image
from pybooru import Danbooru
from pygelbooru import Gelbooru


class NotFound(Exception):
    pass


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)
    return run


async def prepareNhentai(query):
    print(query)
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
