## Credits
The login phase, and the panopto video downloading code are not my own work.
These parts were done by [Arch](https://github.com/ArchGryphon9362)

## Requirements

### Python

If you have pip installed, call `pip install -r requirements.txt`.
If not, install pip and then call it.
If you don't want to use pip, you're smart enough to figure things out.

## CLI Options

Use with the option `-h` or `--help` to view all other available options, or look at the file titled "help" in this repo.

## Problems

For some reason, sometimes, the crawl phase does not actually crawl anything.
You know this has happened when you see `Regenerated crawl.json` right after `Logged in!`.
When this occurs simply stop the program and rerun.
It usually resolves itself.

If you discover any problems or have any suggestions, PLEASE publish a new issue.
I can only test so much.

## How do I run it?

`py blackboard-crawler.py [OPTIONS]`
