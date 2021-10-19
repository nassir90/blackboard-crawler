import json
from dialog import Dialog

json_file = open("crawl.json", "r")
modules = json.load(json_file)
json_file.close()
choices = [("All", "", True)]
for module in modules:
    if module:
        choices.append((module["name"], "", True))

d = Dialog(dialog="dialog")
code, tags = d.checklist("What modules are you interested in?", choices=choices)
