import asyncio
import os
from crawl import crawl
from download import download
from prompt import prompt
import pyppeteer
from pyppeteer import launch
from pyppeteer.page import Page
import getpass
import getopt
import sys

async def try_login(page: Page, username, password):
    await page.goto('https://tcd.blackboard.com/webapps/bb-auth-provider-shibboleth-BBLEARN/execute/shibbolethLogin?authProviderId=_102_1')

    await page.waitForSelector('#username')
    await page.focus('#username')
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyA')
    await page.keyboard.up('Control')
    await page.keyboard.press('Backspace')
    await page.type('#username', username)

    await page.waitForSelector('#password')
    await page.focus('#password')
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyA')
    await page.keyboard.up('Control')
    await page.keyboard.press('Backspace')
    await page.type('#password', password)

    await page.click('.form-button')
    
    try:
        await page.waitForSelector("#username", timeout=1000)
    except Exception:
        return True

    return False

async def main():
    opts, args = getopt.getopt(sys.argv[1:], "hHp", ["help", "headless", "no-indices", "module-regex=", "submodule-regex=", "crawl=", "prompt=", "download="])

    headless = False
    no_downloads = False
    module_regex = ""
    submodule_regex = ""
    should_crawl = None
    should_prompt = None
    should_download = None
    
    for o, a in opts:
        if o in ("-h", "--help"):
            h = open("help", "r")
            print(h.read(), end="")
            h.close()
            return
        elif o in ("-H", "--headless"):
            headless = True
        elif o in ("-U", "--update"):
            no_downloads = True
        elif o == "--module-regex":
            module_regex = a
        elif o == "--submodule-regex":
            submodule_regex = a
        elif o == "--crawl":
            should_crawl = a == 'yes'
        elif o in ('--p', "--prompt"):
            should_prompt = a == 'yes'
        elif o == "--download":
            should_download = a == 'yes'

    browser = await launch(headless=headless, args=['--no-sandbox',  '--disable-setuid-sandbox'])
    page = await browser.newPage()

    failed_attempts = 0

    if os.path.isfile('./credentials'):
        credentials = open('./credentials', 'r').read().split('\n')
        if not await try_login(page, credentials[0], credentials[1]):
            print('The credentials contained in the credentials file are invalid')
            exit()
    else:
        while not await try_login(page, input('TCD Username: '), getpass.getpass('TCD Password: ')):
            failed_attempts += 1
            print("Failed to login. ", end="")
            if failed_attempts < 3:
                print("Try again")
            else:
                print("Exceeded maximum attempts")
                exit()

    print("Logged in!")
    if should_crawl == None:
        should_crawl = not os.path.exists("crawl.json") or input("Crawl.json exists.\n Regenerate? This will take some time. [y/n] ") == "y"
    if should_crawl:
        await crawl(page, module_regex=module_regex, submodule_regex=submodule_regex)
        print("Regenerated 'crawl.json'")

    if should_prompt == None:
        should_prompt = not os.path.exists("choices.json") or input("There is a choices.json here.\n Regenerate? You will have to go through the prompt menu again. [y/n] ") == "y"
    if should_prompt:
        prompt()

    if should_download == None:
        should_download = input("Download files?\n Download? [y/n] ") == 'y'
    if should_download:
        await page.reload()
        await page.waitFor(1000)
        s_session_id = next(filter(lambda cookie: cookie['name'] == 's_session_id', await page.cookies()))['value']
        download('crawl.json', 'choices.json', s_session_id)

debug = os.environ.get('DEBUG_BLACKBOARD_CRAWLER')

if debug == '1':
    import pdb
    pdb.run('asyncio.get_event_loop().run_until_complete(main())')
else:
    asyncio.get_event_loop().run_until_complete(main())
