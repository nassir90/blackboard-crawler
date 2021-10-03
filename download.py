import asyncio
import getpass
import os
import os.path
import sys
import pyppeteer
from pyppeteer import launch
from pyppeteer.browser import Browser
from pyppeteer.network_manager import Response
from pyppeteer.frame_manager import Frame
from pyppeteer.page import Page
import urllib.request
import urllib.parse
import re
import ffmpeg
from subprocess import call
import getopt

failed_attempts = 0

async def try_login(browser: Browser, page: Page):
    global failed_attempts

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

    is_logged_in = False
    cookies = await page.cookies()

    for cookie in cookies:
        if cookie.get('name') in ('shib_idp_session', 's_session_id'):
            is_logged_in = True
    
    if not is_logged_in:
        failed_attempts += 1
        if failed_attempts < 3:
            print('Login failed, please try again')
            print()
            await try_login(browser, page)
        else:
            print('Failed to login, exiting')
            exit()
    else:
        print('Logged In!')
        await page.waitFor(2000)
        await logged_in(browser, page)

async def logged_in(browser: Browser, page: Page):
    await page.goto("https://tcd.blackboard.com/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1")

    await page.waitForSelector(MODULE_LINK)
    for module_index in range(len(await page.JJ(MODULE_LINK))):
        await download_module(module_index, page)
        await page.goto("https://tcd.blackboard.com/webapps/portal/execute/tabs/tabAction?tab_tab_group_id=_2_1")


MODULE_LINK = ".courseListing > li > a"
SUBMODULE_LINK = "#courseMenuPalette_contents li a"
CONTENT = "#content_listContainer > li"
CONTENT_HEADER_LINK = "h3 a"
CONTENT_BODY_LINK = ".details a"
CONTENT_LINK = CONTENT_BODY_LINK + "," + CONTENT_HEADER_LINK
PANOPTO_CONTENT = "a.detail-title"

agreed = False
current_output_dir = ""

async def download_module(index: int, page: Page):
    global agreed
    if (not agreed):
        await page.waitForSelector("#agree_button", timeout=3000)
        await page.click("#agree_button") # Need to accept privacy policy
        agreed = True

    await page.waitForSelector(MODULE_LINK)
    module_link, module_text = await page.JJeval(MODULE_LINK, "(links, index) => [links[index].href, links[index].innerText]", index)
    await page.goto(module_link)

    print("Traversing module #" + str(index) + " : " + module_text)

    global current_output_dir
    current_output_dir = "downloads/" + module_text + "/"
    if not os.path.isdir(current_output_dir):
        os.mkdir(current_output_dir)

    module_root = page.url
    for submodule_index in range(len(await page.JJ(SUBMODULE_LINK))):
        await traverse_submodule(submodule_index, page)
        await page.goto(module_root)

async def traverse_submodule(submodule_index: int, page: Page):
    submodule_link, submodule_text = await page.JJeval(SUBMODULE_LINK, "(links, submodule_index) => [links[submodule_index].href, links[submodule_index].innerText]", submodule_index)
    await page.goto(submodule_link)
    
    print(" Traversing submodule #" + str(submodule_index) + " :" + submodule_text)
    
    await download_content(page, "  ")

async def download_content(page: Page, level: str):
    try:
        await page.waitForSelector(CONTENT, timeout=5000)
        await download_list_content(page, level)
        return
    except Exception as e:
        print (e)

#   Panopt video downloading not currently functional
#
#   try:
#       await page.waitForSelector("iframe", timeout=500)
#       iframe = await page.J("iframe")
#       source = await page.evaluate("iframe => iframe.src", iframe)
#       if "panopto" in source:
#           await download_panopto_content(await iframe.contentFrame(), page, level)
#   except Exception:
#       pass

    print(level + "Not panopto content OR list content")


async def download_list_content(page: Page, level: str):
    content_root = page.url
    for content_index in range(len(await page.JJ(CONTENT))):
        await page.waitForSelector(CONTENT, timeout=2000)
        content = (await page.JJ(CONTENT))[content_index]

        # These are those links which are not contained in the header, i.e. those that we will not traverse
        links = await content.JJeval(".details a", "links => links.map(a => a.href)")
        for link in links:
            if "webapp" not in link:
                await download(link, await page.cookies(), level)

        header_link = await content.J("h3 a")
        await content.hover()
        await page.waitFor(3000)
        if header_link:
            link = await page.evaluate('header_link => header_link.href', header_link)
            if "webapp" not in link:
                await download(link, await page.cookies(), level)
            elif link not in page.url:
                print(level + "Descending into : ")
                print(level + "├" + link)
                print(level + "From : ")
                print(level + "└" page.url)
                await page.goto(link)
                await download_content(page, level + " ")
                await page.goto(content_root)

async def download_panopto_content(frame: Frame, page: Page, level: str):
    await frame.waitForSelector(PANOPTO_CONTENT, timeout=5000)
    for link in await frame.JJ(PANOPTO_CONTENT):
        href = await frame.evaluate("link => link.href", link)
        if "instance=blackboard" not in href:
            href += "&instance=blackboard" 
        await page.goto(href)

        async def on_res(response: Response):
            if response.url == 'https://tcd.cloud.panopto.eu/Panopto/Pages/Viewer/DeliveryInfo.aspx':
                await got_stream_data((await response.json())['Delivery']['Streams'][0]['StreamUrl'])

        page.on('response', lambda res: asyncio.ensure_future(on_res(res)))
        await page.waitForResponse('https://tcd.cloud.panopto.eu/Panopto/Pages/Viewer/DeliveryInfo.aspx')
        await page.waitFor(500)
        
async def got_stream_data(stream_url: str):
    response = urllib.request.urlopen(stream_url)
    data = response.read()
    text = data.decode('utf-8')

    url = re.sub(r"master\.m3u8.*", "", stream_url) + text.splitlines()[3]
    response2 = urllib.request.urlopen(url)
    data2 = response2.read()
    text2 = data2.decode('utf-8')

    ts = current_output_dir + "download.ts"
    mp4 = current_output_dir + "download.mp4"
    
    try:
        os.remove(ts)
    except Exception:
        pass

    try:
        os.remove(mp4)
    except Exception:
        pass

    file_str = open(ts, 'wb')
    for file in re.sub(r"#.*\n", "", text2).splitlines():
        print('Downloading part ' + str(list(map(int, re.findall(r'\d+', file)))[0]) + ' / ' + str(list(map(int, re.findall(r'\d+', re.sub(r"#.*\n", "", text2).splitlines()[-1])))[0]))
        url2 = re.sub(r"master\.m3u8.*", "", stream_url) + text.splitlines()[3].split('/')[0] + '/' + file
        response3 = urllib.request.urlopen(url2)
        
        file_str.write(response3.read())

    file_str.close()
    stream = ffmpeg.input(ts)
    stream = ffmpeg.output(stream, mp4, **{'bsf:a': 'aac_adtstoasc', 'acodec': 'copy', 'vcodec': 'copy'})
    ffmpeg.run(stream)
    
    try:
        os.remove(ts)
    except Exception:
        pass

wget_path = "wget"

async def download(url: str, cookies: list, level: str):
    print(level + "Downloading : " + url)

    s_session_id = next(filter(lambda cookie: cookie['name'] == 's_session_id', cookies))['value']

    global current_output_dir
    olddir = os.getcwd()
    os.chdir(current_output_dir)
    call(wget_path + " --no-clobber --relative --trust-server-names --no-verbose --quiet --show-progress --progress=bar:force --timeout=5 --header 'Cookie: s_session_id=%s'" % s_session_id + " '%s' 2>>errors" % url, shell=True)
    os.chdir(olddir)

async def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hHw:", ["help", "headless", "wget-path"])
    except Exception:
        pass

    headless = False
    
    for o, a in opts:
        if o in ("-h", "--help"):
            print("-h/--help - print this help menu")
            print("-H/--headless - run in headless mode")
            print("-w/--wget-path - the location of the wget binary")
            return
        elif o in ("-H", "--headless"):
            headless = True
        elif o in ("-w", "--wget-path"):
            global wget_path
            wget_path = a

    browser = await launch(headless=headless, args=['--no-sandbox',  '--disable-setuid-sandbox'])
    page = await browser.newPage()
    await page.goto('https://tcd.blackboard.com/webapps/bb-auth-provider-shibboleth-BBLEARN/execute/shibbolethLogin?authProviderId=_102_1')
    if not os.path.isdir("downloads"):
        os.mkdir("downloads")
    await try_login(browser, page)

try:
    asyncio.get_event_loop().run_until_complete(main())
finally:
    pass
