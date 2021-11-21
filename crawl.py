# This file is derived from download.py, except it only produces a crawlfile

import asyncio
import json
import re
import pyppeteer
import traceback
from pyppeteer import launch
from pyppeteer.page import Page
from pyppeteer.network_manager import Response
import urllib3
import getopt

MODULE_LINK = ".courseListing > li > a"
SUBMODULE_LINK = "#courseMenuPalette_contents li a"
CONTENT = "#content_listContainer > li"
CONTENT_HEADER_LINK = "h3 a"
CONTENT_BODY_LINK = ".details a"
CONTENT_LINK = CONTENT_BODY_LINK + "," + CONTENT_HEADER_LINK
PANOPTO_CONTENT = ".content-table a.detail-title"
PANOPTO_SUBFOLDER = ".subfolder-item"

crawlfile_path = "crawl.json"
http = urllib3.PoolManager()

async def traverse_module(module_link: str, module_text: str, page: Page, submodule_regex=""):
    module = {"name" : module_text, "link" : module_link, "submodules" : []};

    print("Traversing module %s" % module_text)
 
    await page.goto(module_link)
    
    try:
        await page.waitForSelector(SUBMODULE_LINK, timeout=5000)
    except:
        print("John Waldron Moment 🗿")
        return module
    
    for submodule_link, submodule_text in await page.JJeval(SUBMODULE_LINK, "links => links.map(link => [link.href, link.innerText])"):
        if re.search(submodule_regex, submodule_text):
            module["submodules"].append(await traverse_submodule(submodule_link, submodule_text, page))

    return module

async def crawl(page: Page, submodule_regex="", module_regex=""):
    modules = []

    await page.goto("https://tcd.blackboard.com/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1")
    await page.waitForSelector("#agree_button", timeout=3000)
    await page.click("#agree_button") # Need to accept privacy policy
    await page.waitForSelector(MODULE_LINK) # Necessary

    for module_link, module_text in await page.JJeval(MODULE_LINK, "links => links.map(link => [link.href, link.innerText])"):
        if re.search(module_regex, module_text):
            modules.append(await traverse_module(module_link, module_text, page, submodule_regex=submodule_regex))
        else:
            print("'%s' does not match '%s', ignoring" % (module_regex, module_text))

    crawlfile = open(crawlfile_path, "w")
    json.dump(modules, crawlfile)

async def traverse_submodule(submodule_link: str, submodule_text: str, page: Page):
    await page.goto(submodule_link)

    submodule = {
        "name" : submodule_text,
        "link" : submodule_link,
        "files" : [],
        "videos" : [],
        "submodules" : [] # AAHHHHH
    }
    
    print(" Traversing submodule '%s' " % submodule_text)
    
    indices = await index(page, "  ")

    submodule["files"] = indices.get("files", [])
    submodule["videos"] = indices.get("videos", [])
    submodule["submodules"] = indices.get("submodules", [])

    return submodule

async def index(page: Page, level: str):
    if "/listContent" in page.url:
        return await traverse_list(page, level)
    elif "/ppto-PanoptoCourseTool-BBLEARN" in page.url:
        await page.goto(await page.Jeval("iframe", "iframe => iframe.src") + '&maxResults=250')
        return await traverse_panopto_list(page, level)
    else:
        print(level + "Unsupported content type")
        return {}

async def traverse_list(page: Page, level: str):
    indices = {"files" : [], "videos" : [], "submodules" : []}

    content_root = page.url
    s_session_id = next(cookie['value'] for cookie in await page.cookies() if cookie['name'] == 's_session_id')
    
    for link, link_text, header in await page.JJeval("%(0)s .details a, %(0)s h3 a" % {'0' : CONTENT}, "links => links.map(a => [a.href, a.innerText, a.parentElement.tagName == 'H3'])"):
        if "tcd.cloud.panopto.eu" in link:
            print(level + "Found video : '%s' at '%s'" % (link_text, link))
            try:
                aspxauth = next(cookie['value'] for cookie in await page.cookies() if cookie['name'] == '.ASPXAUTH')
                stream_url = get_stream_url(link, aspxauth)
            except Exception as e:
                print(level + "└Failed to get master.m3u8 for video: " + link)
                continue
            indices["videos"].append({'name' : link_text, 'link' : stream_url})
            await page.goto(content_root)
        elif "webapps" not in link:
            indices["files"].append(get_real_filename(link, s_session_id, level))
        elif header and link not in page.url:
            print(level + "Descending into : '%s'" % link_text)
            await page.goto(link)
            indices["submodules"].append(await index(page, level + " "))
            await page.goto(content_root)

    return indices

async def traverse_panopto_list(page: Page, level: str):
    await page.waitFor(3000)
    indices = { "files": [], "videos": [], "submodules": [] }

    folders = await page.JJ(PANOPTO_SUBFOLDER)
    print(level + 'There are %d folders' % len(folders))
    links = await page.JJeval(PANOPTO_CONTENT, "links => links.map(link => [link.href, link.innerText])")
    print (level + "There are %d videos " % len(links))
    aspxauth = next(cookie['value'] for cookie in await page.cookies() if cookie['name'] == '.ASPXAUTH')
    for link, link_text in links:
        if link_text and link:
            print(level + 'Found video \'%s\'' % link_text)
            stream_url = get_stream_url(link, aspxauth)
            video = {'name': link_text, 'link' : stream_url}
            indices['videos'].append(video)

    return indices

def get_stream_url(link: str, aspxauth: str):
    delivery_id = re.search('(?<=id=)[^&]*', link).group(0)
    response = http.request(
        'GET'
        'https://tcd.cloud.panopto.eu/Panopto/Pages/Viewer/DeliveryInfo.aspx',
        fields={'deliveryId':delivery_id, 'responseType':'json'},
        headers={"Cookie" : ".ASPXAUTH="+aspxauth},
        timeout=2
    )
    return json.load(response.data)['Delivery']['Streams'][0]['StreamUrl'] # This may raise KeyError if the JSON returned is invalid

def get_real_filename(url: str, s_session_id: str, level: str):
    if "bbcswebdav" in url:
        try:
            response = http.request(
                'GET',
                url,
                retries=False,
                headers={"Cookie":"s_session_id="+s_session_id}
            )
            url = "tcd.blackboard.com" + response.headers['Location']
        except Exception as e:
            print(level + str(e))
    
    print(level + "Found file : " + url)
    return url
