from __future__ import print_function, unicode_literals
from PyInquirer import prompt as iprompt, print_json, Separator
import re
import json
from blackboard_crawler_constants import VALID_TYPES

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

def prompt(type_choices, input_path="crawl.json", output_path="choices.json"):
    json_file = open(input_path, "r")
    modules = json.load(json_file)
    json_file.close()
    # Dictionary containing module entries, which contain submodule entries.
    # Submodule entries are associated with a boolean which indicates whether the submodule is to be downloaded or not.
    module_choices = { module["name"] : {  submodule["name"] : True for submodule in module["submodules"] } for module in modules}

    last_selection = ""

    while True:
        questions = [
            {
                'type' : 'list',
                'name' : 'selected_module',
                'message' : 'What module do you wish to configure?',
                'choices' : ['Configure Types of File to Download', Separator()] + ["%s (%s)" % (module, module_status(submodule_choices)) for module, submodule_choices in module_choices.items()] + [Separator(), 'Finish']
            }
        ]

        selected_module = iprompt(questions)['selected_module']

        if 'Finish' == selected_module:
            break
        elif 'Configure Types' in selected_module:
            type_questions = [
                {
                    'type' : 'checkbox',
                    'name' : 'selected_types',
                    'message' : 'Select types',
                    'choices' : [ {'name' : t, 'checked' : type_choices[t] } for t in type_choices ]
                }
            ]

            selected_types = iprompt(type_questions)['selected_types']

            for t in type_choices:
                type_choices[t] = False
            for t in selected_types:
                type_choices[t] = True
        else:
            module = re.sub(r' \(.*\)', '', selected_module)
            submodule_choices = module_choices[module]

            submodule_questions = [ 
                {
                    'type' : 'checkbox',
                    'name' : 'selected_submodules',
                    'message' : 'What submodules would you like to download?',
                    'choices' : [ { 'name' : submodule_name, 'checked' : submodule_choices[submodule_name]} for submodule_name in submodule_choices]
                }
            ]

            selected_submodules = iprompt(submodule_questions)['selected_submodules']
            for submodule_name in submodule_choices:
                submodule_choices[submodule_name] = False
            for submodule_name in selected_submodules:
                submodule_choices[submodule_name] = True

    json.dump({ 'module_choices' : module_choices, 'type_choices' : type_choices}, open(output_path, 'w'))
    
