import json
from dialog import Dialog

NOT_DOWNLOADING = "Not Downloading"
DOWNLOADING = "Downloading Fully"
DOWNLOADING_PARTIALLY = "Downloading Partially"

def module_status(submodule_choices):
    total_number_of_submodules = len(submodule_choices)
    selected_submodules = len(list(filter(lambda selected: selected, submodule_choices.values())))
    if selected_submodules == total_number_of_submodules:
        return DOWNLOADING
    elif selected_submodules == 0:
        return NOT_DOWNLOADING
    else:
        return DOWNLOADING_PARTIALLY

json_file = open("crawl.json", "r")
modules = json.load(json_file)
json_file.close()

module_choices = { module["name"] : {  submodule["name"] : True for submodule in module["submodules"] } for module in modules}


d = Dialog(dialog="dialog")
while True:
    choices = [(module_name, module_status(module)) for module_name, module in module_choices.items()]
    code, choice = d.menu("What modules are you downloading?", width=100, choices=choices)

    if code != d.OK:
        break

    code, response = d.menu(choice, choices=[(DOWNLOADING, ""), (DOWNLOADING_PARTIALLY, ""), (NOT_DOWNLOADING, "")])
    if code == d.OK:
        submodules = module_choices[choice]
        if response == DOWNLOADING_PARTIALLY:
            code, submodule = d.menu("What submodules are you downloading?", choices=[(name, DOWNLOADING if downloading else NOT_DOWNLOADING) for name, downloading in module_choices[choice].items()])
            if code == d.OK:
                code, response = d.menu(choice, choices=[(DOWNLOADING, ""), (NOT_DOWNLOADING, "")])
                if code == d.OK:
                    if response == DOWNLOADING:
                        submodules[submodule] = True
                    else:
                        submodules[submodule] = False
        else:
            downloading = response == DOWNLOADING
            for submodule in submodules:
                submodules[submodule] = downloading

pruned_crawl = {}

for module in modules:
    pruned_crawl[module['name']] = {}
    pruned_crawl[module['name']]['submodules'] = list(filter(lambda submodule: module_choices[module['name']][submodule['name']] == True, module['submodules']))

json.dump(pruned_crawl, open("pruned_crawl.json", "w"))
