import asyncio
import os
from crawl import crawl
from download import download
import pyppeteer
from pyppeteer import launch
from pyppeteer.page import Page
import getpass
import getopt
import sys

async def try_login(page: Page):
    await page.goto('https://tcd.blackboard.com/webapps/bb-auth-provider-shibboleth-BBLEARN/execute/shibbolethLogin?authProviderId=_102_1')

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
    
    try:
        await page.waitForSelector("#username", timeout=1000)
    except Exception:
        return True

    return False

async def main():
    opts, args = getopt.getopt(sys.argv[1:], "hH0", ["help", "headless", "no-indices", "module-regex=", "submodule-regex="])

    headless = False
    no_downloads = False
    module_regex = ""
    submodule_regex = ""
    
    for o, a in opts:
        if o in ("-h", "--help"):
            print("-h/--help - print this help menu")
            print("-H/--headless - run in headless mode")
            print("-0/-U/--update - regenerate the crawlfile and exit")
            print("--module-regex - only crawl modules that match the regex")
            print("--submodule-regex - only crawl submodules that match the regex")
            return
        elif o in ("-H", "--headless"):
            headless = True
        elif o in ("-0", "-U", "--update"):
            no_downloads = True
        elif o == "--module-regex":
            module_regex = a
        elif o == "--submodule-regex":
            submodule_regex = a

    browser = await launch(headless=headless, args=['--no-sandbox',  '--disable-setuid-sandbox'])
    page = await browser.newPage()

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
    if not os.path.exists("crawl.json") or no_downloads or input("Crawl.json exists. Are you sure you want to regenerate the crawlfile? This will take some time: [y/n]") == "y":
        await crawl(page, module_regex=module_regex, submodule_regex=submodule_regex)
        print("Regenerated 'crawl.json'")

    if not no_downloads:
        await page.reload()
        await page.waitFor(1000)
        s_session_id = next(filter(lambda cookie: cookie['name'] == 's_session_id', await page.cookies()))['value']
        download('crawl.json', s_session_id)

asyncio.get_event_loop().run_until_complete(main())

# Will run three steps
# Check if crawl.json is here
# Prompt.should_recrawl?
#   Login here if the user wants to recrawl
# Prompt.pruned_crawlfile
# Download(pruned_crawlfile)
#  Login here if the user didn't recrawl
