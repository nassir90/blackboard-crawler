import json
import traceback
import os
import os.path
import urllib.request
import urllib.parse
import re
import ffmpeg

current_output_dir = ""
crawlfile_path = "crawl.json"
        
def download_panopto_stream(stream_url: str, link_text: str, level: str):
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
            print(level + 'Downloading part %d/%d' % (int(ts_file.strip(".ts")),  total_parts))
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

def download_file(url: str, s_session_id: str, level: str):
    request = urllib.request.Request(url)
    request.add_header("Cookie", "s_session_id=" + s_session_id)
    try:
        response = urllib.request.urlopen(request, timeout=3)
    except Exception as e:
        print(level + "└" + str(e))
        return
    output_file_path = os.path.basename(urllib.parse.unquote(response.url))
    if not output_file_path:
        output_file_path = os.path.basename(response.url.strip("/"))
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

def download_submodule(submodule: dict, s_session_id: str, level: str, type_choices: dict):
    if type_choices['documents'] | type_choices['other']:
        for file in submodule.get('files', []):
            print(level + "Downloading : " + file)
            download_file(file, s_session_id, level)
    if type_choices['videos']:
        for video in submodule.get('videos', []):
            print(level + "Downloading video '%s'" % video['name'])
            download_panopto_stream(video['link'], video['name'], level + " ")
    for submodule in submodule.get('submodules', []):
        if submodule:
            download_submodule(submodule, s_session_id, level + " ")

def download(crawl_path: str, choices_path: str, s_session_id: str, type_choices: dict):
    choices_file = open(choices_path, "r")
    crawl_file = open(crawl_path, "r")
    choices = json.load(choices_file)
    modules = json.load(crawl_file)
    choices_file.close()
    crawl_file.close()
    module_choices = choices['module_choices']
    type_choices = choices['type_choices']

    pruned_crawl = []
    for module in modules:
        pruned_crawl.append({'name' : module['name'], 'submodules' : [submodule for submodule in module['submodules'] if module_choices[module['name']][submodule['name']]] })

    if not os.path.exists("downloads"):
        os.mkdir("downloads")
    os.chdir("downloads")
    downloads_dir = os.getcwd()
    for module in pruned_crawl:
        print("Downloading module '%s'" % module['name'])
        if not os.path.exists(module['name']):
            os.mkdir(module['name'])
        os.chdir(module['name'])
        for submodule in module['submodules']:
            print(" Downloading submodule '%s'" % submodule['name'])
            download_submodule(submodule, s_session_id, "  ", type_choices)
        os.chdir(downloads_dir)
