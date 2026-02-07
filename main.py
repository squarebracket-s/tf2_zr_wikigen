import os, util


WIKI_FILES = {}
if "waveset" in util.SCOPE:
    import modules.wavesets
    WIKI_FILES = modules.wavesets.parse() | WIKI_FILES # Merges WIKI_FILES dict with those of the wavesets module

if "items" in util.SCOPE:
    import modules.weapon
    WIKI_FILES = modules.weapon.parse() | WIKI_FILES

if "skilltree" in util.SCOPE:
    import modules.skilltree
    WIKI_FILES = modules.skilltree.parse() | WIKI_FILES

# Move files to wiki
if os.path.isdir("tf2_zr_wikigen.wiki/"):
    for file in WIKI_FILES:
        if os.path.isfile(file):
            os.rename(file, f"tf2_zr_wikigen.wiki/{WIKI_FILES[file]}")
        else:
            util.log(f"Missing file {file}: cannot move into wiki","WARNING")