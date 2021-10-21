## Credits
The login phase, and the panopto video downloading code are not my own work.
These parts were done by [Arch](https://github.com/ArchGryphon9362)

## Requirements

### Python

If you have pip installed, call `pip install -r requirements.txt`.
If not, install pip and then call it.
If you don't want to use pip, you're smart enough to figure things out.

### Dialog

Linux users should use their package managers to install `dialog`.

MacOS users should do the same, e.g. by using `brew install dialog`.

I am currently unsure how `dialog` can be installed on windows.
Windows users will have to settle for selecting all modules unitl I find a cross platform solution (PyInquirer looks good) or I find out how to install `dialog` on the OS.

Windows users can also use the `--module-regex`/`--submodule-regex` options and then crawl for a similar effect.
Note that the choices.json file produced after selecting all modules is very easy to manipulate, so modifying it by hand is also an option.

## CLI Options

Use with the option `-h` or `--help` to view all other available options, or look at the file titled "help" in this repo.

## How do I run it?

`py blackboard-crawler.py [OPTIONS]`
