import asyncio
import json
import traceback
import getpass
import os
import os.path
import sys
import pyppeteer
from pyppeteer import launch
from pyppeteer.browser import Browser
from pyppeteer.network_manager import Response
from pyppeteer.page import Page
import urllib.request
import urllib.parse
import re
import ffmpeg
import getopt

pyppeteer.DEBUG = True  

MODULE_LINK = ".courseListing > li > a"
SUBMODULE_LINK = "#courseMenuPalette_contents li a"
CONTENT = "#content_listContainer > li"
CONTENT_HEADER_LINK = "h3 a"
CONTENT_BODY_LINK = ".details a"
CONTENT_LINK = CONTENT_BODY_LINK + "," + CONTENT_HEADER_LINK
PANOPTO_CONTENT = "a.detail-title"

current_output_dir = ""
crawlfile_path = "crawl.json"
agreed_to_cookies = False
no_downloads = False

async def try_login(page: Page):
    await page.waitForSelector('#username')

    await page.focus('#username')
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyA')
    await page.keyboard.up('Control')
    await page.keyboard.press('Backspace')

    await page.type('#username', input('TCD Username: '))
    await page.waitForSelector('#password')

    await page.focus('#password')
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyA')
    await page.keyboard.up('Control')
    await page.keyboard.press('Backspace')

    await page.type('#password', getpass.getpass('TCD Password: '))
    await page.click('.form-button')

    for cookie in await page.cookies():
        if cookie.get('name') in ('shib_idp_session', 's_session_id'):
            return True

    return False

async def crawl(page: Page):
    modules = []

    await page.waitFor(2000)
    await page.goto("https://tcd.blackboard.com/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1")
    
    root_dir = os.getcwd()
    await page.waitForSelector(MODULE_LINK)

    for module_index in range(len(await page.JJ(MODULE_LINK))):
        modules.append(await traverse_module(module_index, page))
        await page.goto("https://tcd.blackboard.com/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1")
        os.chdir(root_dir)

    crawlfile = open(crawlfile_path, "w")
    json.dump(modules, crawlfile)

async def traverse_module(index: int, page: Page):
    global agreed_to_cookies
    if not agreed_to_cookies:
        await page.waitForSelector("#agree_button", timeout=3000)
        await page.click("#agree_button") # Need to accept privacy policy
        agreed_to_cookies = True

    await page.waitForSelector(MODULE_LINK)
    module_link, module_text = await page.JJeval(MODULE_LINK, "(links, index) => [links[index].href, links[index].innerText]", index)
    module = {
        "name" : module_text,
        "link" : module_link,
        "submodules" : []
    };

    if "MATH" in module_text:
        print("Traversing module #%d : %s" % (index, module_text))
    else:
        print("Skipping module #%d : %s" % (index, module_text))
        return

    await page.goto(module_link)

    global current_output_dir
    current_output_dir = os.getcwd() + "/downloads/" + module_text + "/"
    if not os.path.isdir(current_output_dir):
        os.mkdir(current_output_dir)

    module_root = page.url
    for submodule_index in range(len(await page.JJ(SUBMODULE_LINK))):
        module["submodules"].append(await traverse_submodule(submodule_index, page))
        await page.goto(module_root)

    return module


async def traverse_submodule(submodule_index: int, page: Page):
    submodule_link, submodule_text = await page.JJeval(SUBMODULE_LINK, "(links, submodule_index) => [links[submodule_index].href, links[submodule_index].innerText]", submodule_index)
    submodule = {
        "name" : submodule_text,
        "link" : submodule_link,
        "files" : [],
        "panoptoVideos" : [],
        "submodules" : [] # AAHHHHH
    }

    await page.goto(submodule_link)
    
    print(" Traversing submodule #" + str(submodule_index) + " :" + submodule_text)
    
    downloads = await download(page, "  ")
    if downloads:
        if downloads.get("files"):
            submodule["files"] = downloads["files"]
        if downloads.get("panoptoVideos"):
            submodule["panoptoVideos"] = downloads["panoptoVideos"]
        if downloads.get("submodules"):
            submodule["submodules"] = downloads["submodules"]

    return submodule

async def download(page: Page, level: str):
    if "/listContent" in page.url:
        return await traverse_list(page, level)
    elif "/ppto-PanoptoCourseTool-BBLEARN" in page.url:
        await page.goto(await page.Jeval("iframe", "iframe => iframe.src"))
        return await traverse_panopto_list(page, level)
    elif "/announcement" in page.url:
        print(level + "Downloading and storing announcements is not supported yet")
    else:
        print(level + "Not panopto content OR list content")

async def traverse_list(page: Page, level: str):
    downloads = {"files" : [], "videos" : [], "submodules" : []}

    content_root = page.url
    for content_index in range(len(await page.JJ(CONTENT))):
        await page.waitForSelector(CONTENT, timeout=2000)
        content = (await page.JJ(CONTENT))[content_index]

        # These are those links which are not contained in the header, i.e. those that we will not traverse
        links = await content.JJeval(".details a", "links => links.map(a => a.href)")
        for link in links:
            if "webapp" not in link:
                downloads["files"].append(await download_file(link, await page.cookies(), level))

        header_link = await content.J("h3 a")
        if header_link:
            link, link_text = await page.evaluate('header_link => [header_link.href, header_link.innerText]', header_link)
            if "webapp" not in link:
                downloads["files"].append(await download_file(link, await page.cookies(), level))
            elif link not in page.url:
                print(level + "Descending into : '%s'" % link_text)
                await page.goto(link)
                downloads["submodules"].append(await download(page, level + " "))
                await page.goto(content_root)

    return downloads

async def traverse_panopto_list(page: Page, level: str):
    downloads = { "files": [], "videos": [], "submodules": [] }
    await page.waitForSelector(PANOPTO_CONTENT, timeout=5000)
    await page.waitFor(3000)
    print (level + "There are %d videos " % len(await page.JJ(PANOPTO_CONTENT)))
    for link, link_text in await page.JJeval(PANOPTO_CONTENT, "links => links.map(link => [link.href, link.innerText])"):
        if link:
            downloads["videos"].append({
                "name" : link_text,
                "link" : link
            })
            await download_panopto_video(link, link_text, page)
    return downloads

async def download_panopto_video(link: str, link_text: str, page: Page):
    global no_downloads
    if no_downloads:
        print("Found panopto video : " + link_text)
        return

    async def on_res(response: Response, link_text: str):
        if response.url == 'https://tcd.cloud.panopto.eu/Panopto/Pages/Viewer/DeliveryInfo.aspx':
            await got_stream_data((await response.json())['Delivery']['Streams'][0]['StreamUrl'], link_text)

    page.on('response', lambda res: asyncio.ensure_future(on_res(res, link_text)))

    if "instance=blackboard" not in link:
        link += "&instance=blackboard" 

    await page.goto(link)

    await page.waitForResponse('https://tcd.cloud.panopto.eu/Panopto/Pages/Viewer/DeliveryInfo.aspx')
        
async def got_stream_data(stream_url: str, link_text: str):
    master_response = urllib.request.urlopen(stream_url)
    master_data = master_response.read()
    master = master_data.decode('utf-8')

    first_master_entry = re.findall(r"\d+/index\.m3u8", master, re.MULTILINE)[0]

    url = re.sub(r"master\.m3u8.*", "", stream_url) + first_master_entry
    index_response = urllib.request.urlopen(url)
    index_data = index_response.read()
    index = index_data.decode('utf-8')

    ts = current_output_dir + link_text.strip() + ".ts"
    mp4 = current_output_dir + link_text.strip() + ".mp4"

    output_ts = open(ts, 'wb')
    ts_files = re.sub(r"#.*\n", "", index).splitlines()
    total_parts = int(ts_files[-1].strip(".ts")) # Very hacky, may change later
    for ts_file in ts_files:
        if ts_file:
            print('Downloading part %d/%d' % (int(ts_file.strip(".ts")),  total_parts))
            part_url = re.sub(r"master\.m3u8.*", first_master_entry.split('/')[0] + '/' + ts_file, stream_url)
            part_response = urllib.request.urlopen(part_url)
            output_ts.write(part_response.read())

    output_ts.close()

    stream = ffmpeg.input(ts)
    stream = ffmpeg.output(stream, mp4, **{'bsf:a': 'aac_adtstoasc', 'acodec': 'copy', 'vcodec': 'copy'})
    ffmpeg.run(stream)
    
    try:
        os.remove(ts)
    except Exception:
        pass

async def download_file(url: str, cookies: list, level: str):
    global no_downloads
    if no_downloads:
        print(level + "Found : " + url)
        return url

    s_session_id = next(filter(lambda cookie: cookie['name'] == 's_session_id', cookies))['value']

    global current_output_dir
    olddir = os.getcwd()
    os.chdir(current_output_dir)
    
    request = urllib.request.Request(url)
    request.add_header("Cookie", "s_session_id=" + s_session_id)

    try:
        response = urllib.request.urlopen(request)
    except Exception as e:
        print(level + str(e))
        return url

    print(level + "Downloading : " + response.url)

    output_file_path = os.path.basename(response.url)
    temp_file_path = output_file_path + ".uncompleted-write"

    if not os.path.isfile(output_file_path):
        print(level + "└" + output_file_path + " does not exist. Downloading...")
        data = response.read()
        temp_file = open(temp_file_path, "wb")
        temp_file.write(data)
        temp_file.close()
        os.rename(temp_file_path, output_file_path)
    else:
        print(level + "└" + output_file_path + " exists. Not downloading!")

    os.chdir(olddir)

    return response.url

async def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hH0", ["help", "headless", "no-downloads"])
    except Exception:
        pass

    global no_downloads
    headless = False
    
    for o, a in opts:
        if o in ("-h", "--help"):
            print("-h/--help - print this help menu")
            print("-H/--headless - run in headless mode")
            print("-0/--no-downloads - don't actually download any files. Just output their links")
            return
        elif o in ("-0", "--no-downloads"):
            no_downloads = True
        elif o in ("-H", "--headless"):
            headless = True

    browser = await launch(headless=headless, args=['--no-sandbox',  '--disable-setuid-sandbox'])
    page = await browser.newPage()
    await page.goto('https://tcd.blackboard.com/webapps/bb-auth-provider-shibboleth-BBLEARN/execute/shibbolethLogin?authProviderId=_102_1')
    if not os.path.isdir("downloads"):
        os.mkdir("downloads")

    failed_attempts = 0

    while not await try_login(page):
        failed_attempts += 1
        print("Failed to login. ", end="")
        if failed_attempts < 3:
            print("Try again")
        else:
            print("Exceeded maximum attempts")
            exit()

    print("Logged in!")
    await crawl(page)

try:
    asyncio.get_event_loop().run_until_complete(main())
finally:
    pass
