# This file is derived from download.py, except it only produces a crawlfile

import asyncio
import json
import getpass
import sys
import pyppeteer
import traceback
from pyppeteer import launch
from pyppeteer.page import Page
from pyppeteer.network_manager import Response
import urllib.request
import getopt

pyppeteer.DEBUG = True  

MODULE_LINK = ".courseListing > li > a"
SUBMODULE_LINK = "#courseMenuPalette_contents li a"
CONTENT = "#content_listContainer > li"
CONTENT_HEADER_LINK = "h3 a"
CONTENT_BODY_LINK = ".details a"
CONTENT_LINK = CONTENT_BODY_LINK + "," + CONTENT_HEADER_LINK
PANOPTO_CONTENT = "a.detail-title"

crawlfile_path = "crawl.json"
agreed_to_cookies = False

async def traverse_module(module_link: str, module_text: str, page: Page, submodule_regex=""):
    module = {"name" : module_text, "link" : module_link, "submodules" : []};

    print("Traversing module %s" % module_text)
 
    await page.goto(module_link)
    
    try:
        await page.waitForSelector(SUBMODULE_LINK, timeout=1000)
    except:
        print("John Waldon Moment 🗿")
        return module

    
    for submodule_link, submodule_text in await page.JJeval(SUBMODULE_LINK, "links => links.map(link => [link.href, link.innerText])"):
        if submodule_regex in submodule_text:
            module["submodules"] = [await traverse_submodule(submodule_link, submodule_text, page)]

    return module

async def crawl(page: Page, submodule_regex="", module_regex=""):
    modules = []

    await page.waitFor(1000)
    await page.goto("https://tcd.blackboard.com/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1")
    
    print("Here")

    await page.waitForSelector("#agree_button", timeout=3000)
    await page.click("#agree_button") # Need to accept privacy policy
    agreed_to_cookies = True
    
    print("HERE")

    for module_link, module_text in await page.JJeval(MODULE_LINK, "links => links.map(link => [link.href, link.innerText])"):
        if module_regex in module_text:
            modules.append(await traverse_module(module_link, module_text, page, submodule_regex=submodule_regex))

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
        await page.goto(await page.Jeval("iframe", "iframe => iframe.src"))
        return await traverse_panopto_list(page, level)
    else:
        print(level + "Unsupported content type")
        return {}

async def traverse_list(page: Page, level: str):
    indices = {"files" : [], "videos" : [], "submodules" : []}

    content_root = page.url
    
    for link, link_text, header in await page.JJeval("%(0)s .details a, %(0)s h3 a" % {'0' : CONTENT}, "links => links.map(a => [a.href, a.innerText, a.parentElement.tagName == 'H3'])"):
        if "webapps" not in link:
            indices["files"].append(await get_real_filename(link, await page.cookies(), level))
        elif header and link not in page.url:
            print(level + "Descending into : '%s'" % link_text)
            await page.goto(link)
            indices["submodules"].append(await index(page, level + " "))
            await page.goto(content_root)

    return indices

async def traverse_panopto_list(page: Page, level: str):
    indices = { "files": [], "videos": [], "submodules": [] }
    await page.waitForSelector(PANOPTO_CONTENT, timeout=5000)
    await page.waitFor(1000)
    print (level + "There are %d videos " % len(await page.JJ(PANOPTO_CONTENT)))
    for link, link_text in await page.JJeval(PANOPTO_CONTENT, "links => links.map(link => [link.href, link.innerText])"):
        if link_text and link:
            if "instance=blackboard" not in link:
                link += "&instance=blackboard" 

            await page.goto(link)

            response = await page.waitForResponse('https://tcd.cloud.panopto.eu/Panopto/Pages/Viewer/DeliveryInfo.aspx')
            video = {'name': link_text, 'link' : (await response.json())['Delivery']['Streams'][0]['StreamUrl'] }

            indices["videos"].append(video)

    return indices

async def get_real_filename(url: str, cookies: list, level: str):
    if "bbcswebdav" in url:
        s_session_id = next(filter(lambda cookie: cookie['name'] == 's_session_id', cookies))['value']
        request = urllib.request.Request(url)
        request.add_header("Cookie", "s_session_id=" + s_session_id)
        try:
            response = urllib.request.urlopen(request, timeout=5)
            url = response.url
        except Exception as e:
            print(level + str(e))
    
    print(level + "Found : " + url)
    return url
