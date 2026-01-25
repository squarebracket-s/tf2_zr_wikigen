import os
import pathlib
from keyvalues1 import KeyValues1
from collections import defaultdict
import vtf2img
import re

# https://stackoverflow.com/questions/2082152/how-to-make-a-case-insensitive-dictionary
from requests.structures import CaseInsensitiveDict

import util

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

BUILTIN_IMG = "https://raw.githubusercontent.com/squarebracket-s/tf2_zr_wikigen/refs/heads/main/builtin_img/"
ICON_DOWNLOAD = util.md_img(BUILTIN_IMG+"download.svg", "download")
ICON_X_SQUARE = util.md_img(BUILTIN_IMG+"x-square.svg","cross")
ICON_MUSIC = util.md_img(BUILTIN_IMG+"music.svg","music")
FLAG_MAPPINGS = {
    "MVM_CLASS_FLAG_NONE": "",
    "MVM_CLASS_FLAG_NORMAL": "Normal",
    "MVM_CLASS_FLAG_SUPPORT": "Support",
    "MVM_CLASS_FLAG_MISSION": "<mark>Support</mark>",
    "MVM_CLASS_FLAG_MINIBOSS": "Miniboss",
    "MVM_CLASS_FLAG_ALWAYSCRIT": "Crits",
    "MVM_CLASS_FLAG_SUPPORT_LIMITED": "Limited Support",
}


## COMPILE WAVESETS -------------------------------------------------------------------------------------------------
def remove_multiline_comments(d): # Fixes the script interpreting the comment in npc_headcrabzombie.sp as actual data
    new_str = ""
    reading_comment = False
    for line in d.splitlines():
        if line == "/*": reading_comment=True
        if line == "*/": reading_comment=False
        if not reading_comment:
            new_str += line
    return new_str


def compile_waveset_npc():
    def extract_npc_data(path):
        util.debug(f"Parsing NPC {path}","OKCYAN")
        file_data = util.read(path)
        file_data = remove_multiline_comments(file_data)
        if ("npc_donoteveruse" not in file_data and "NPC_Add" in file_data):
            # Get name
            name = file_data.split("	strcopy(data.Name, sizeof(data.Name), \"")[1].split("\");")[0]
            
            # Get plugin and health
            # TODO: Case for non-shared file with multiple NPC_Add calls (-> different npc names) Example: raidmode_bosses/npc_god_alaxios.sp (sea-infected god alaxios isn't present in any redsun cfg!)
            def parse_health_number(num):
                try:
                    float(num)
                    return num
                except ValueError:
                    # Assume variable
                    npc_vars = file_data.split("#define ")
                    npc_vars_dict = {}
                    for i, item in enumerate(npc_vars):
                        if i > 0:
                            # May parse whole blocks of code as key&value pairs sometimes, but it gets the job done. Doesn't break actual variables in any way
                            full_str = item.split('"')
                            k, v = util.normalize_whitespace(full_str[0]).replace(" ",""), full_str[1].replace(" ","")
                            npc_vars_dict[k] = v

                    if num in npc_vars_dict:
                        util.debug(f"[X] {path} var {num}")
                        return npc_vars_dict[num]
                    else:
                        util.debug(f"[ ] {path} var {num}")
                        return "dynamic"
            if "shared" in path:
                # Several instances of NPC entry data, several instances of CClotBody in separate files
                plugin = file_data.split("	strcopy(data.Plugin, sizeof(data.Plugin), \"")
                plugin = [item.split("\");")[0] for i,item in enumerate(plugin) if i > 0]

                category = file_data.split("	data.Category = ")
                category = [item.split(";")[0] for i,item in enumerate(category) if i > 0]

                flags = file_data.split("	data.Flags = ")
                flags = [item.split(";")[0].split("|") for i,item in enumerate(flags) if i > 0]

                base_path = path.replace(path.split("/")[-1],"") # remove deepest item
                health = []
                for i,p in enumerate(plugin):
                    p_data = util.read(base_path+p+".sp")
                    try:
                        health = file_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
                        if "MinibossHealthScaling" in health:
                            health = f"Miniboss health scaling (Base {health.split("(")[1][:-1]}HP)"
                        elif ":" in health:
                            """
                            extra "data" fields for enemies (lists, numbers or types like "Elite")
                            'data[0]?x' is probably checking if any value from the waveset cfg exists at all to use x? 
                            """
                            cases = health.split(":(")
                            if len(cases) == 0: cases = health.split(":")
                            health = {}
                            def parse_case(c):
                                if "?" in c:
                                    k,v = c.split("?")
                                    if k.startswith("data"): k="any"
                                else:
                                    k,v = "default", c
                                v=v.replace(")","")
                                return k,v
                            for case in cases:
                                if ":" in case:
                                    subcases = case.split(":")
                                    for subcase in subcases:
                                        k,v = parse_case(subcase)
                                        health[k] = parse_health_number(v)
                                else:
                                    k,v = parse_case(case)
                                    health[k] = parse_health_number(v)
                        else:
                            health = parse_health_number(health) + "HP"
                    except IndexError:
                        h = "?"
                    health.append(h)
                
                filetype = "shared"
            if file_data.count("NPC_Add") > 1:
                # Several instances of NPC entry data, one instance of CClotBody
                plugin = file_data.split("	strcopy(data.Plugin, sizeof(data.Plugin), \"")
                plugin = [item.split("\");")[0] for i,item in enumerate(plugin) if i > 0]

                category = file_data.split("	data.Category = ")
                category = [item.split(";")[0] for i,item in enumerate(category) if i > 0]

                flags = file_data.split("	data.Flags = ")
                flags = [item.split(";")[0].split("|") for i,item in enumerate(flags) if i > 0]
            
                try:
                    health = file_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
                    if "MinibossHealthScaling" in health:
                        health = f"Miniboss health scaling (Base {health.split("(")[1][:-1]}HP)"
                    elif ":" in health:
                        """
                        extra "data" fields for enemies (lists, numbers or types like "Elite")
                        'data[0]?x' is probably checking if any value from the waveset cfg exists at all to use x? 
                        """
                        cases = health.split(":(")
                        if len(cases) == 0: cases = health.split(":")
                        health = {}
                        def parse_case(c):
                            if "?" in c:
                                k,v = c.split("?")
                                if k.startswith("data"): k="any"
                            else:
                                k,v = "default", c
                            v=v.replace(")","")
                            return k,v
                        for case in cases:
                            if ":" in case:
                                subcases = case.split(":")
                                for subcase in subcases:
                                    k,v = parse_case(subcase)
                                    health[k] = parse_health_number(v)
                            else:
                                k,v = parse_case(case)
                                health[k] = parse_health_number(v)
                    else:
                        health = parse_health_number(health) + "HP"
                except IndexError:
                    health = "?"
                filetype = "multi"
            else:
                # One instance of everything
                try:
                    health = file_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
                    if "MinibossHealthScaling" in health:
                        health = f"Miniboss health scaling (Base {health.split("(")[1][:-1]}HP)"
                    elif ":" in health:
                        """
                        extra "data" fields for enemies (lists, numbers or types like "Elite")
                        'data[0]?x' is probably checking if any value from the waveset cfg exists at all to use x? 
                        """
                        cases = health.split(":(")
                        if len(cases) == 0: cases = health.split(":")
                        health = {}
                        def parse_case(c):
                            if "?" in c:
                                k,v = c.split("?")
                                if k.startswith("data"): k="any"
                            else:
                                k,v = "default", c
                            v=v.replace(")","")
                            return k,v
                        for case in cases:
                            if ":" in case:
                                subcases = case.split(":")
                                for subcase in subcases:
                                    k,v = parse_case(subcase)
                                    health[k] = parse_health_number(v)
                            else:
                                k,v = parse_case(case)
                                health[k] = parse_health_number(v)
                    else:
                        health = parse_health_number(health) + "HP"
                except IndexError:
                    health = "?"
                plugin = file_data.split("	strcopy(data.Plugin, sizeof(data.Plugin), \"")[1].split("\");")[0]

                try:
                    category = file_data.split("	data.Category = ")[1].split(";")[0]
                except IndexError:
                    category = ""
                
                try:
                    flags = file_data.split("	data.Flags = ")[1]
                    flags = flags.split(";")[0].split("|")
                except IndexError:
                    flags = []
                
                filetype = "single"

            # Get icon
            try:
                icon = file_data.split("	strcopy(data.Icon, sizeof(data.Icon), \"")[1].split("\");")[0]
            except IndexError:
                icon = ""

            
            desc_key = f"{name} Desc"
            if desc_key in PHRASES_NPC:
                description = PHRASES_NPC[desc_key]["en"].replace("\\n","  \n")
            elif desc_key in PHRASES_NPC_2:
                description = PHRASES_NPC_2[desc_key]["en"].replace("\\n","  \n")
            else:
                description = ""
            
            npc_obj = {
                "name": name,
                "category": category,
                "description": description, 
                "plugin": plugin, 
                "icon": icon, 
                "health": health, 
                "flags": flags,
                "filetype": filetype
            }

            return True, npc_obj
        return False, None

    def parse_all_npcs():
        npc_by_file = {}
        for file in pathlib.Path(PATH_NPC).glob('**/*'):
            if os.path.isfile(file.absolute()):
                add, data = extract_npc_data(str(file.absolute()))
                if add:
                    plugin_name = data["plugin"]
                    if type(plugin_name) == list:
                        for i,pn in enumerate(plugin_name):
                            pn_data = data.copy()
                            if data["filetype"] == "shared":
                                pn_data["health"] = pn_data["health"][min(len(pn_data["health"])-1,i)]
                            pn_data["category"] = pn_data["category"][min(len(pn_data["category"])-1,i)]
                            pn_data["plugin"] = pn_data["plugin"][min(len(pn_data["plugin"])-1,i)]
                            pn_data["flags"] = pn_data["flags"][min(len(pn_data["flags"])-1,i)]
                            npc_by_file[pn] = pn_data
                    else:                    
                        npc_by_file[plugin_name] = data

        if "DEBUG" in os.environ:
            try:
                if bool(os.environ["DEBUG"]):
                    import json
                    util.write("npc_data.json",json.dumps(npc_by_file,indent=2))
            except ValueError:
                util.log("DEBUG env couldn't be converted to bool!","WARNING")
        return npc_by_file
    

    def unique_enemy_delays(w):
        # Make each wave delay unique as not to lose out on info (for example if 2 enemies have same wave delay)
        # https://stackoverflow.com/questions/41941116/replace-each-occurrence-of-sub-strings-in-the-string-with-randomly-generated-val
        space = "		"
        for i in range(0,301):
            delay_str = f'{i/10:.1f}'
            delay_count = w.count(delay_str)
            w = w.replace("{","{{").replace("}","}}") # double curly brackets get ignored by .format
            w = w.replace(f'{space}"{delay_str}"', space+'"{}"')
            w = w.format(*(" "*i + delay_str for i in range(delay_count)))
        return w
    

    def parse_waveset_list_cfg(cfg, md_npc, md_mapsets):
        WAVESET_LIST = KeyValues1.parse(util.read(f"./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/{cfg}"))
        
        if "Setup" not in WAVESET_LIST and "Custom" not in WAVESET_LIST: # Unsupported waveset cfg (Rogue, Bunker, etc.)
            util.log(f"Unsupported waveset cfg {cfg}!","WARNING")
            return md_npc, md_mapsets
        util.log(f"Parsing waveset list cfg: {cfg}")

        map_mode = "Custom" in WAVESET_LIST
        if map_mode: # map-specific waveset list config
            WAVESET_LIST = WAVESET_LIST["Custom"]
        
        WAVESET_LIST = WAVESET_LIST["Setup"]


        if "Waves" in WAVESET_LIST:
            wavesets = WAVESET_LIST["Waves"]
        else: # Assume data being in the cfg file itself. See: maps/zr_bossrush.cfg
            wavesets = WAVESET_LIST

        MARKDOWN_WAVESETS = f"Starting cash: ${WAVESET_LIST["cash"]}  \n{"# Wavesets"*int(not map_mode)}  \n"
        if not map_mode:
            for waveset_name in wavesets:
                MARKDOWN_WAVESETS += f"- [{waveset_name}](#{util.to_section_link(waveset_name)})  \n"
        else:
            n = cfg.split("/")[-1].replace(".cfg","")
            md_mapsets += f"- [{n}]({n}.md)  \n"
        
        if "Modifiers" in WAVESET_LIST:
            MARKDOWN_WAVESETS += f"# Modifiers  \n"
            for modifiers in WAVESET_LIST["Modifiers"]:
                MARKDOWN_WAVESETS += f"- [{modifiers}](#{util.to_section_link(modifiers)})  \n"    
        
        for waveset_name in wavesets:
            self_destruct = False
            if "file" in wavesets[waveset_name]:
                waveset_file = wavesets[waveset_name]["file"]
                util.log(f"    {waveset_name}{" "*(35-len(waveset_name))}| {waveset_file}")
                wave_cfg = util.read(f"./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/{waveset_file}.cfg")
                # Waveset-specific typo fixes (or just removing lines that break the parser)
                if waveset_file == "classic_iber&expi": wave_cfg=wave_cfg.replace('			"plugin"	"110000000"',"") # overrides actual plugin name before it, which is why it has to be removed
                wave_cfg = unique_enemy_delays(wave_cfg)

                WAVESET_DATA = KeyValues1.parse(wave_cfg)["Waves"]

                if "desc" in wavesets[waveset_name]:
                    waveset_desc_key = wavesets[waveset_name]["desc"]
                    # Blame artvin PR #895 for not translating a desc
                    if waveset_desc_key in PHRASES_WAVESET:
                        desc = PHRASES_WAVESET[waveset_desc_key]["en"].replace("\\n","  \n")
                    else:
                        desc = waveset_desc_key
                else:
                    desc = ""
                MARKDOWN_WAVESETS += f"# {waveset_name}  \n[Back to top](#wavesets)  \n{desc}  \n"
            else:
                self_destruct = True
                WAVESET_DATA = wavesets
            
            wd = defaultdict(str,WAVESET_DATA)
            a_npc = f"NPC Author{"s" * int("," in wd["author_npcs"])}: {wd["author_npcs"]}  \n" if wd["author_npcs"] != "" else ""
            a_format = f"Format Author{"s" * int("," in wd["author_format"])}: {wd["author_format"]}  \n" if wd["author_format"] != "" else ""
            a_raid = f"Raid Author{"s" * int("," in wd["author_raid"])}: {wd["author_raid"]}  \n" if wd["author_raid"] != "" else ""
            MARKDOWN_WAVESETS += f"{a_npc}{a_format}{a_raid}"
            
            for wave in WAVESET_DATA:
                wave_data = WAVESET_DATA[wave]
                try:
                    int(wave) # Check if key can be converted to a number to detect wave notation
                except ValueError:
                    if wave.startswith("music_"):
                        music_case = wave.split("_")[1].capitalize()
                        music = f"{wave_data["name"]} by {wave_data["author"]}"
                        mfilename = wave_data["file"].replace("#","")
                        if mfilename == "vo/null.mp3": continue
                        file = f"[{ICON_DOWNLOAD}](https://raw.githubusercontent.com/artvin01/TF2-Zombie-Riot/refs/heads/master/sound/{mfilename})"
                        if not os.path.isfile(f"./TF2-Zombie-Riot/sound/{mfilename}"): file = ICON_X_SQUARE
                        MARKDOWN_WAVESETS += f"{ICON_MUSIC} **{music_case}:** {music} {file}  \n"
                    continue
                if len(wave_data)==0: continue
                MARKDOWN_WAVESETS += f"## {wave}  \n"
                for wave_entry in wave_data:
                    wave_entry_data = wave_data[wave_entry]
                    try:
                        float(wave_entry)
                    except ValueError:
                        if wave_entry.startswith("music_"):
                            icon = util.md_img(BUILTIN_IMG+"music.svg","M2")
                            if type(wave_entry_data) == str:
                                mfilename = wave_entry_data.replace("#","")
                                music = mfilename
                                try: int(wave_entry_data); continue # skip if not actual music entry e.g. "music_outro_duration"	"65"
                                except ValueError: pass
                            else:
                                wave_entry_data = defaultdict(str,wave_entry_data)
                                name = wave_entry_data["file"].replace("#","")
                                if wave_entry_data["name"] != "": name = wave_entry_data["name"]
                                if wave_entry_data["author"] != "": author = f"by {wave_entry_data["author"]}"
                                else: author = ""
                                music = f"{name} {author}"
                                mfilename = wave_entry_data["file"].replace("#","")
                            file = f"[{ICON_DOWNLOAD}](https://raw.githubusercontent.com/artvin01/TF2-Zombie-Riot/refs/heads/master/sound/{mfilename})"
                            if not os.path.isfile(f"./TF2-Zombie-Riot/sound/{mfilename}"): file = ICON_X_SQUARE
                            MARKDOWN_WAVESETS += f"{ICON_MUSIC} {music.replace("_","\\_")} {file}  \n"
                        continue
                    count = "always 1" if wave_entry_data["count"] == "0" else wave_entry_data["count"]
                    npc_data = NPCS_BY_FILENAME[wave_entry_data["plugin"]]

                    npc_name = npc_data["name"]
                    npc_name_prefix = ""

                    # Health data
                    """
                    bool carrier = data[0] == 'R';
                    bool elite = !carrier && data[0];
                    """
                    extra_info = ""
                    if "health" in wave_entry_data:
                        extra_info += f" {wave_entry_data["health"]}HP"
                    else:
                        if type(npc_data["health"]) == dict:
                            if "data" in wave_entry_data:
                                data_key = wave_entry_data["data"]
                                # vars
                                carrier = data_key[0] == "R"
                                elite = (not carrier) and data_key[0] # If first char isn't R but data exists

                                if carrier: data_key = "carrier"
                                elif elite: data_key = "elite"
                                else: data_key = "default";npc_name_prefix="!c"

                                if data_key not in npc_data["health"] and "any" in npc_data["health"]: data_key = "any";
                                elif data_key not in npc_data["health"]: data_key = "default";

                                npc_name_prefix += wave_entry_data["data"].capitalize()
                                util.debug(f"Parsing HP Value{npc_data["health"]} DATA value {wave_entry_data["data"]} CHOSEN value {data_key}", "OKCYAN")
                                h = f" {npc_data["health"][data_key.lower()]}"
                            else:
                                h = npc_data["health"]["default"]
                            extra_info += f" {h}HP"
                        else:
                            extra_info += f" {npc_data["health"]}"
                    
                    # Show NPC Flags
                    for flag in npc_data["flags"]:
                        if flag != "0" and flag != "-1":
                            extra_info += f" {FLAG_MAPPINGS[flag]}"
                    
                    # Show if NPC is scaled
                    if "force_scaling" in wave_entry_data:
                        if wave_entry_data["force_scaling"]=="1":
                            extra_info += " _(forcibly scaled)_"
                    

                    # Get icon
                    if npc_data["icon"]!="":
                        npc_icon_key = "leaderboard_class_"+npc_data["icon"]+".vtf"
                        npc_png_icon_path = f"repo_img/{npc_data["icon"]}.png"
                        
                        # Paths to look in for icons
                        npc_icon_path = f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}"
                        raw_npc_icon_path = f"./TF2-Zombie-Riot/dev_files_donot_use_for_server/hud_icons/WIP/RawClassIcons/leaderboard_class_{npc_data["icon"]}.png"
                        if os.path.isfile(npc_icon_path):
                            if not os.path.isfile(npc_png_icon_path):
                                npc_icon = vtf2img.Parser(f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}").get_image()
                                npc_icon.save(npc_png_icon_path)
                            image = util.md_img(npc_png_icon_path,"A")
                        elif os.path.isfile(raw_npc_icon_path):
                            if not os.path.isfile(npc_png_icon_path): # Local testing has persistent env
                                os.rename(raw_npc_icon_path, npc_png_icon_path)
                            image = util.md_img(npc_png_icon_path,"C")
                        elif os.path.isfile(npc_png_icon_path): # Local testing has persistent env
                            image = util.md_img(npc_png_icon_path,"D")
                        else:
                            image = util.md_img("./builtin_img/missing.png","E")
                    else:
                        image = util.md_img("./builtin_img/missing.png","F")

                    # Add NPC to wave data                
                    if npc_data["category"] != "Type_Hidden":
                        MARKDOWN_WAVESETS += f"{count} {image} {npc_name_prefix} [{npc_name}](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/NPCs#{"-"+npc_name.lower().replace(" ","-").replace(",","")}) {extra_info}  \n"
                        # Add NPC if not hidden & doesn't exist already
                        if wave_entry_data["plugin"] not in added_npc_ids:
                            added_npc_ids.append(wave_entry_data["plugin"])
                            if type(npc_data["health"]) == dict:
                                npc_health = ""
                                for k,v in npc_data["health"].items():
                                    npc_health += f"{k.capitalize()}: {v}HP"
                            else:
                                npc_health = f"Default health: {npc_data["health"]}  \n" if npc_data["health"] != "" else ""
                            npc_cat = f"Category: {npc_data["category"]}  \n" if npc_data["category"] != "" else ""
                            if "0" not in npc_data["flags"] and "-1" not in npc_data["flags"]:
                                npc_flags = "Flags: "
                                dflags = ", ".join([FLAG_MAPPINGS[item] for item in npc_data["flags"]])
                                npc_flags += dflags + "  \n"
                            else:
                                npc_flags = ""
                            md_npc += f"# {image.replace("16","32")} {npc_name}  \n_{wave_entry_data["plugin"]}_  \n{npc_health}{npc_flags}{npc_cat}{npc_data["description"]}  \n"
                    else:
                        MARKDOWN_WAVESETS += f"{count} {image} {npc_name} {extra_info}  \n"

            if self_destruct: break

        if "Modifiers" in WAVESET_LIST:
            for modifier in WAVESET_LIST["Modifiers"]:
                data = WAVESET_LIST["Modifiers"][modifier]
                desc = PHRASES_NPC_2[data["desc"]]["en"].replace("\\n","  \n")
                MARKDOWN_WAVESETS += f"# {modifier}  \n[Back to top](#modifiers)  \nMinimum level: {float(data["level"])*1000}  \n{desc}  \n"

        if map_mode:
            display_name = cfg.split("/")[-1].replace(".cfg","")
            filename = display_name + ".md"
        else:
            filename = f"wavesets_{cfg}.md".replace("/","_")
            disp = cfg.replace(".cfg","").replace("_"," ").replace("/"," ")
            disp_title = disp.replace("'","~").title().replace("~","'") # https://stackoverflow.com/a/1549644
            display_name = f"{disp_title}.md"
        WIKI_FILES[filename] = display_name
        util.write(filename, MARKDOWN_WAVESETS)
        return md_npc, md_mapsets

    # TODO: Map-specific wavesets such as Matrix (stored in addons/sourcemod/zombie_riot/config/maps/)
    # NPC list is global to prevent duplicates
    PATH_NPC = "./TF2-Zombie-Riot/addons/sourcemod/scripting/zombie_riot/npc/"
    MARKDOWN_NPCS = ""
    MARKDOWN_MAPSETS = "\n**Map-specific wavesets**  \n"
    added_npc_ids = []

    if not os.path.isdir("repo_img"): os.system("mkdir repo_img")

    PHRASES_NPC = CaseInsensitiveDict(KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.zombienames.txt"))["Phrases"])
    PHRASES_NPC_2 = CaseInsensitiveDict(KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.item.gift.desc.txt"))["Phrases"])
    PHRASES_WAVESET = CaseInsensitiveDict(KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.txt"))["Phrases"])

    util.log("Parsing NPCs...")
    NPCS_BY_FILENAME = parse_all_npcs()

    cfg_files = [
        "classic.cfg",
        "fastmode.cfg",
        "fastmode_redsun.cfg", 
    ]
    for file in os.listdir("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/maps/"):
        if ".cfg" in file:
            cfg_files.append(f"maps/{file}")

    for f in cfg_files:
        MARKDOWN_NPCS, MARKDOWN_MAPSETS = parse_waveset_list_cfg(f, MARKDOWN_NPCS, MARKDOWN_MAPSETS)

    util.write("npcs.md", MARKDOWN_NPCS)
    util.write("sidebar.md", util.read("wiki/sidebar.md")+MARKDOWN_MAPSETS)
    util.write("home.md", util.read("wiki/home.md")+MARKDOWN_MAPSETS)

## COMPILE WEAPON CFG -------------------------------------------------------------------------------------------------

def compile_weapon():
    util.log("Compiling Weapon List...")
    MARKDOWN_WEAPON = ""
    MARKDOWN_WEAPON_PAP = ""
    tags = []
    CFG_WEAPONS = KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/weapons.cfg"))["Weapons"]
    PHRASES_WEAPON = KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.weapons.description.txt"))["Phrases"]
    
    def is_item_category(c):
        return "enhanceweapon_click" not in c and "cost" not in c


    def is_weapon(c):
        return "desc" in c or "author" in c


    def is_trophy(c):
        return "desc" in c and "visual_desc_only" in c


    def is_category(c):
        return "author" not in c and "filter" in c and "whiteout" not in c

    def extract_pap_data(weapon_name, weapon_data, idx):
        pap_key = f"pap_{idx}_"
        key_desc = pap_key+"desc"
        if key_desc in weapon_data:
            key_customname = pap_key + "custom_name"
            if key_customname in weapon_data: pap_name = weapon_data[key_customname]
            else: pap_name = weapon_name
            
            pap_desc = weapon_data[key_desc]

            pap_cost = weapon_data[pap_key+"cost"]

            if pap_key+"tags" in weapon_data: pap_tags = " ".join(f"#{tag}" for tag in weapon_data[pap_key+"tags"].split(";") if tag != "")
            else: pap_tags = ""

            # There has got to a better way to do this
            key_papskip = pap_key+"papskip"
            if key_papskip in weapon_data: pap_skip = weapon_data[key_papskip]
            else: pap_skip = "0"

            key_pappaths = pap_key+"pappaths"
            if key_pappaths in weapon_data: pap_paths = weapon_data[key_pappaths]
            else: pap_paths = "1"

            key_extra_desc = pap_key+"extra_desc"
            if key_extra_desc in weapon_data: pap_extra_desc = weapon_data[key_extra_desc]
            else: pap_extra_desc = ""

            pap_attributes = weapon_data[pap_key+"attributes"]

            return {"name": pap_name, "description": pap_desc, "extra_desc": pap_extra_desc, "cost": pap_cost, "tags": pap_tags, "_skip": pap_skip, "_paths": pap_paths, "_attributes": pap_attributes}
        return None
    
    def pap_data_to_md(data,depth):
        if data["description"] in PHRASES_WEAPON:
            desc = PHRASES_WEAPON[data["description"]]["en"]
        else:
            desc = data["description"] # some paps don't have translation for whatever reason lmao
        
        extra_desc = data["extra_desc"] if len(data["extra_desc"]) > 0 else ""
        space_header = " "*depth
        space = " "*round(depth*1.5) # Scale a bit to align with header spacing

        if len(data["tags"])>0: tags = f"{space}{data["tags"]}  \n"
        else: tags = ""

        return f"### {space_header} {data["name"]} \\[{util.id_from_str(data["_attributes"])}\\]  \n{tags}{space}${data["cost"]}  \n{space}{desc.replace("\\n",f"  \n{space}")}  \n{space}{extra_desc.replace("\\n",f"  \n{space}")}"

    def pap_data_to_link(data):
        return f"[{data["name"]}](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/Weapon_Paps#{util.to_section_link(data["name"],True)}-{util.id_from_str(data["_attributes"])})  \n"


    def interpret_weapon_paps(weapon_name,weapon_data):
        """
        pap_#_pappaths define how many paps you can choose from below ("2" paths on "PaP 1" allows you to choose between "PaP 2" and "PaP 3")
        pap_#_papskip Skips a number of paps to choose ("1" skip on "PaP 1" allows you to choose "PaP 3" instead)
        """
        pap_idx = 0
        pap_md = ""
        pap_links = ""
        def item_block(parent_pap,idx,md,links,DEPTH):
            for i in range(int(parent_pap["_paths"])):
                idx += 1
                if int(parent_pap["_paths"])>1:
                    md += f"## {" "*DEPTH} _Path {i+1}_  \n"
                    links += f"{" "*DEPTH} _Path {i+1}_  \n"
                pd = extract_pap_data(weapon_name,weapon_data,idx)#+int(parent_pap["_skip"]))
                if pd:
                    md += pap_data_to_md(pd,DEPTH)
                    links += (" "*DEPTH) + pap_data_to_link(pd)
                    if pd["_paths"]!="0": md, links = item_block(pd, idx+int(pd["_skip"]), md, links,DEPTH+1)
            return md, links
        # eugh
        pap_md += f"# {weapon_name}  \n[Back to weapon](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/Items#{util.to_section_link(weapon_name)})  \n"
        if "pappaths" in weapon_data: init_pap_paths = weapon_data["pappaths"]
        else: init_pap_paths = 1
        pap_links = "**Paps**  \n"
        pap_md, pap_links = item_block({"_skip": "0", "_paths": init_pap_paths}, pap_idx, pap_md, pap_links, 0)
        return pap_md, pap_links


    def parse_weapon_data(weapon_name, weapon_data, depth, gtags):
        if "tags" in weapon_data:
            taglist = weapon_data["tags"].split(";")
            if "," in weapon_data["tags"]: taglist = weapon_data["tags"].split(",") # crystal shard uses commas instead of semicolons. blame artvin
            tags = " ".join(f"#{tag}" for tag in taglist if tag != "" and len(tag)>2)
            for tag in taglist:
                if tag.capitalize() not in gtags and tag not in gtags and len(tag)>2: gtags.append(tag)
        else: tags = ""

        if "author" in weapon_data: author = f"Author: {weapon_data["author"]}"
        else: author = ""

        cost = "$" + weapon_data["cost"]

        if "desc" in weapon_data: 
            k = weapon_data["desc"]
            if k in PHRASES_WEAPON:
                description = PHRASES_WEAPON[k]["en"]
            else: # this only exists because of the Infinity Blade
                description = k
            description = description.replace("\\n","  \n").replace("\n-","\n - ") + "  \n"
            if description.startswith("-"): description=" - "+description[1:]
        else: description = ""

        pap_md, pap_links = interpret_weapon_paps(weapon_name,weapon_data)
        
        return f"##{"#"*depth} {weapon_name}  \n{tags}  \n{author}  \n{cost}  \n{description}  \n{pap_links}  ", pap_md, gtags


    def item_block(key,data,depth,markdown,markdown_pap,tags):
        if "hidden" not in data:
            depth += 1
            markdown += f"#{"#"*depth} {key}  \n"
            for item in data:
                item_data = data[item]
                if is_trophy(item_data):
                    markdown += f"Trophy: {item}  \n"
                elif is_weapon(item_data):
                    m1, m2, tags = parse_weapon_data(item,item_data,depth,tags)
                    markdown += m1
                    markdown_pap += m2
                elif item[0].isupper() and is_category(item_data) or "Perks" in item or "Trophies"==item: # unneeded data is always lowercase...
                    markdown, markdown_pap, tags = item_block(item, item_data, depth, markdown, markdown_pap, tags)
                elif "whiteout" in item_data:
                    markdown += f"Info: {item}  \n"
        return markdown, markdown_pap, tags


    for item_category in CFG_WEAPONS:
        if is_item_category(CFG_WEAPONS[item_category]):
            MARKDOWN_WEAPON, MARKDOWN_WEAPON_PAP, tags = item_block(item_category,CFG_WEAPONS[item_category],0,MARKDOWN_WEAPON,MARKDOWN_WEAPON_PAP, tags)
    
    taglist_str = "  \n".join({f" - #{tag}" for tag in tags})
    MARKDOWN_WEAPON = f"**Available tags:** \n{taglist_str}  \n"+MARKDOWN_WEAPON

    util.write("items.md", MARKDOWN_WEAPON)
    util.write("weapon_paps.md", MARKDOWN_WEAPON_PAP)

## COMPILE SKILLTREE CFG -------------------------------------------------------------------------------------------------

def compile_skilltree():
    util.log("Compiling Skilltree...")
    """
    	"name"		"Luck Up 1"	// Name
        "player"	"SkillPlayer_LuckUp"	// Function
    //	"weapon"	"Tree_LuckUp"	// Functio	n
        "max"	"5"	// Max Charges	
        "cost"	"1"	// Point Cos	t
    //	"min"	"-1"	// Charge Required from Paren	t
    //	"key"	""	// Inventory Item Required
    """
    SKILLTREE_CFG = KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/skilltree.cfg"))
    # strange formatting of the string I know
    MARKDOWN_SKILLTREE = """## Legend
- MIN: Minimum amount of ranks needed in parent skill to unlock  
- MAX: Maximum rank  
- COST: Amount of points needed per rank  
- REQ: Required item to unlock skill

```mermaid
    %%{init:{'theme':'forest'}}%%
    mindmap"""
    def skill_block(x,y,skill,parent_skill_key,skill_md,depth):
        depth += 1
        for subskill in skill.keys():
            if subskill.startswith("a"): # detect if key is an actual skill
                data = skill[subskill]

                if "min" in data: min_pts = f"\nMIN {data["min"]}"
                else: min_pts = ""

                if "key" in data: required_item = f"\nREQ {data["key"]}"
                else: required_item = ""

                if "cost" in data: cost = f"\nCOST {data["cost"]}"
                else: cost = ""

                desc = f"{data["name"]}{cost}\nMAX {data["max"]}{min_pts}{required_item}"
                skill_md += f'{" "*depth}{subskill}["{desc}"]\n'
                skill_md = skill_block(x,y,data,subskill,skill_md,depth)
        return skill_md
    
    MARKDOWN_SKILLTREE = skill_block(0,0,SKILLTREE_CFG,list(SKILLTREE_CFG.keys())[0],MARKDOWN_SKILLTREE,0)
    MARKDOWN_SKILLTREE += "```"
    util.write("skilltree.md", MARKDOWN_SKILLTREE)

compile_weapon()
compile_waveset_npc()
compile_skilltree()

# Move files to wiki
if os.path.isdir("tf2_zr_wikigen.wiki/"):
    for file in WIKI_FILES:
        if os.path.isfile(file):
            os.rename(file, f"tf2_zr_wikigen.wiki/{WIKI_FILES[file]}")
        else:
            util.log(f"Missing file {file}: cannot move into wiki","WARNING")