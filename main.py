import modules.weapon
import modules.wavesets
import modules.skilltree

import os, util

# Utility functions
# U+3164 -> 'ㅤ'
# also ' '
WIKI_FILES = {
    "items.md": "Items.md",
    "weapon_paps.md": "Weapon_Paps.md",
    "npcs.md": "NPCs.md",
    "skilltree.md": "Skilltree.md",
    "sidebar.md": "_Sidebar.md",
    "home.md": "Home.md"
}

WIKI_FILES = modules.wavesets.parse() | WIKI_FILES # Merges WIKI_FILES dict with those of the wavesets module
modules.weapon.parse()
modules.skilltree.parse()

# Move files to wiki
if os.path.isdir("tf2_zr_wikigen.wiki/"):
    for file in WIKI_FILES:
        if os.path.isfile(file):
            os.rename(file, f"tf2_zr_wikigen.wiki/{WIKI_FILES[file]}")
        else:
            util.log(f"Missing file {file}: cannot move into wiki","WARNING")