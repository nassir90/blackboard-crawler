import os
import re

class File:
    location = ""
    name = ""

    def __init__(self, location: str, name: str):
        self.location = location
        self.name = name

class PanoptoVideo:
    name = ""
    master_location = ""

    def __init__(self, master_location: str, name: str):
        self.master_location = master_location
        self.name = name

class Module:
    name = ""
    link = ""
    files = []
    panopt_videos = []
    modules = []

    def __init__(self, link: str, name: str):
        self.link = link
        self.name = name

data = open("crawlfile", "r")
lines = data.read().splitlines()
for line_number in range(len(lines))
    line = lines[line_number].strip()
    if line[0] == "#":
        continue
    try:
        command = line.split()[0]
    except Exception:
        pass
    arguments = map(lambda string: re.sub('"', "", string), re.findall(r'"[^"]*"', line))

    if command == "MODULE"
