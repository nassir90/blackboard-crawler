from __future__ import print_function, unicode_literals
from PyInquirer import prompt, print_json
import json

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

def prompt(input_path="crawl.json", output_path="choices.json"):
    json_file = open(input_path, "r")
    modules = json.load(json_file)
    json_file.close()

    # A dictionary containing module entries, which contain submodule entries.
    # Submodule entries are associated with a boolean which indicates whether the submodule is to be downloaded or not.
    module_choices = { module["name"] : {  submodule["name"] : True for submodule in module["submodules"] } for module in modules}

    questions = [
        {
            'type' : 'input',
            'name' : 'first_name',
            'message' : 'What\'s your first name?'
        }
    ]

    answers = prompt(questions)
    print_json(answers)




