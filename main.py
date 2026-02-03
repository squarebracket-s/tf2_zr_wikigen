import os, util

util.log("Importing modules...")
import modules.weapon
import modules.wavesets
import modules.skilltree



WIKI_FILES = {}
#WIKI_FILES = modules.wavesets.parse() | WIKI_FILES # Merges WIKI_FILES dict with those of the wavesets module
WIKI_FILES = modules.weapon.parse() | WIKI_FILES
WIKI_FILES = modules.skilltree.parse() | WIKI_FILES

# Move files to wiki
if os.path.isdir("tf2_zr_wikigen.wiki/"):
    for file in WIKI_FILES:
        if os.path.isfile(file):
            os.rename(file, f"tf2_zr_wikigen.wiki/{WIKI_FILES[file]}")
        else:
            util.log(f"Missing file {file}: cannot move into wiki","WARNING")