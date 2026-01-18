import os
from keyvalues1 import KeyValues1
import vtf2img
import re
import json

# Utility functions
# U+3164 -> 'ㅤ'

def read(filename):
    try:
        with open(filename, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return None


def write(filename, val):
    with open(filename, 'w+') as f:
        f.write(str(val))
    return True


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
    print("Compiling Wavesets...")

    def extract_npc_data(path):
        file_data = read(path)
        if ("npc_donoteveruse" not in file_data and "NPC_Add" in file_data):
            file_data = remove_multiline_comments(file_data)
            # Get name
            name = file_data.split("	strcopy(data.Name, sizeof(data.Name), \"")[1].split("\");")[0]
            
            # Get plugin and health
            if "shared" in path:
                plugin = file_data.split("	strcopy(data.Plugin, sizeof(data.Plugin), \"")
                plugin = [item.split("\");")[0] for i,item in enumerate(plugin) if i > 0]

                base_path = path.replace(path.split("/")[-1],"") # remove deepest item
                health = []
                for p in plugin:
                    p_data = read(base_path+p+".sp")
                    try:
                        h = p_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
                        if h == "GetBuildingHealth()" or h == "health":
                            h = "[dynamic]"
                        elif "MinibossHealthScaling" in h:
                            h = f"dynamically scaled (Base {h.split("(")[1][:-1]}HP)"
                        else:
                            h = h + "HP"
                    except IndexError:
                        h = "?"
                    health.append(h)
            else:
                # TODO: Handle cases e.g. carrier?4500:(elite?5000:4000)HP, data[0]?3750:3000HP, elite?7200:5700HP
                try:
                    health = file_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
                    if health == "GetBuildingHealth()" or health == "health":
                        health = "[dynamic] HP"
                    elif "MinibossHealthScaling" in health:
                        health = f"dynamically scaled (Base {health.split("(")[1][:-1]}HP)"
                    else:
                        health = health + "HP"
                except IndexError:
                    health = "?"
                plugin = file_data.split("	strcopy(data.Plugin, sizeof(data.Plugin), \"")[1].split("\");")[0]
            # Get icon
            try:
                icon = file_data.split("	strcopy(data.Icon, sizeof(data.Icon), \"")[1].split("\");")[0]
            except IndexError:
                icon = ""

            
            desc_key = f"{name} Desc"
            if desc_key in PHRASES_NPC:
                description = PHRASES_NPC[desc_key]["en"].replace("\\n","\n")
            elif desc_key in PHRASES_NPC_2:
                description = PHRASES_NPC_2[desc_key]["en"].replace("\\n","\n")
            else:
                description = ""
            return True, {"name": name, "description": description, "plugin": plugin, "icon": icon, "health": health}
        return False, None


    def _parse_npc_subdir_02(path):
        CORE_WALK = os.walk(path)
        l = list(CORE_WALK)[0]
        # Result:
        # [root_dir, directories, files]
        # Put all files into one list (including those in subdirs)
        files = []
        files.extend(l[2]) # Own files
        for subdir in l[1]:
            subdir_files = list(os.walk(path+subdir+"/"))[0][2]
            for f in subdir_files:
                files.append(subdir+"/"+f)
        return files


    def _parse_npc_subdir_01(path):
        sorted_npc_files = {}
        CORE_WALK = os.walk(path)
        l = list(CORE_WALK)[0]
        # Result:
        # [root_dir, directories, files]
        
        # Map directories & files to dict
        directories = l[1]
        for dir_ in directories:
            sorted_npc_files[dir_] = []
            files = _parse_npc_subdir_02(path+dir_+"/")
            for f in files:
                sorted_npc_files[dir_].append(dir_+"/"+f)
        sorted_npc_files[""] = l[2]
        
        # Parse dict
        extracted_npc_data = {}
        for cat in sorted_npc_files.keys():
            for npc_file in sorted_npc_files[cat]:
                add_npc,npc_data = extract_npc_data(path+npc_file)
                if add_npc: extracted_npc_data[npc_file] = npc_data
        return extracted_npc_data
    

    def parse_all_npcs():
        dir_npc_category_list = os.listdir(PATH_NPC)
        npc_by_file = {}
        # TODO: use os.walk instead of whatever the hell this is
        for category in dir_npc_category_list:
            data = _parse_npc_subdir_01(PATH_NPC + category + "/")
            for npc_file in data:
                plugin_name = data[npc_file]["plugin"]
                if type(plugin_name) == type([]):
                    for i,pn in enumerate(plugin_name):
                        pn_data = data[npc_file].copy()
                        pn_data["health"] = pn_data["health"][i]
                        npc_by_file[pn] = pn_data
                else:                    
                    npc_by_file[plugin_name] = data[npc_file]
        #write("npc_data.json",json.dumps(npc_by_file,indent=2))
        return npc_by_file
    

    def unique_enemy_delays(w):
        # Make each wave delay unique as not to lose out on info (for example if 2 enemies have same wave delay)
        # https://stackoverflow.com/questions/41941116/replace-each-occurrence-of-sub-strings-in-the-string-with-randomly-generated-val
        space = "		"
        incl = ""
        for i in range(0,301):
            delay_str = f'{i/10:.1f}'
            incl += delay_str + "\n"
            delay_count = w.count(delay_str)
            w=w.replace("{","{{")
            w=w.replace("}","}}")
            w=w.replace(f'{space}"{delay_str}"', space+'"{}"')
            w = w.format(*(" "*i + delay_str for i in range(delay_count)))
        return w


    PATH_NPC = "./TF2-Zombie-Riot/addons/sourcemod/scripting/zombie_riot/npc/"
    MARKDOWN_WAVESETS = "# Outline\n"
    MARKDOWN_NPCS = ""
    added_npc_ids = []

    PHRASES_NPC = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.zombienames.txt"))["Phrases"]
    PHRASES_NPC_2 = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.item.gift.desc.txt"))["Phrases"]
    PHRASES_WAVESET = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.txt"))["Phrases"]
    WAVESET_LIST = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/fastmode_redsun.cfg"))["Setup"]

    NPCS_BY_FILENAME = parse_all_npcs()

    for waveset_name in WAVESET_LIST["Waves"]:
        MARKDOWN_WAVESETS += f"- [{waveset_name}](#{waveset_name.lower().replace(" ","-")})\n"
    
    for waveset_name in WAVESET_LIST["Waves"]:
        wave_cfg = read(f"./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/{WAVESET_LIST["Waves"][waveset_name]["file"]}.cfg")
        wave_cfg = unique_enemy_delays(wave_cfg)
        WAVESET_DATA = KeyValues1.parse(wave_cfg)["Waves"]
        waveset_desc_key = WAVESET_LIST["Waves"][waveset_name]["desc"]
        MARKDOWN_WAVESETS += f"# {waveset_name.replace(" ","-")}\n{PHRASES_WAVESET[waveset_desc_key]["en"].replace("\\n","\n")}\n"
        for wave in WAVESET_DATA:
            try:
                int(wave) # Check if key can be converted to a number to detect wave notation
            except ValueError:
                continue
            MARKDOWN_WAVESETS += f"## {wave}\n"
            wave_data = WAVESET_DATA[wave]
            for wave_entry in wave_data:
                try:
                    float(wave_entry)
                except ValueError:
                    continue
                wave_entry_data = wave_data[wave_entry]
                count = "1" if wave_entry_data["count"] == "0" else wave_entry_data["count"]
                npc_data = NPCS_BY_FILENAME[wave_entry_data["plugin"]]
                extra_info = ""
                if "health" in wave_entry_data:
                    extra_info += f" {wave_entry_data["health"]}HP"
                else:
                    extra_info += f" {npc_data["health"]}"
                if "force_scaling" in wave_entry_data:
                    if wave_entry_data["force_scaling"]=="1":
                        extra_info += " _(scaled)_"
                npc_name = npc_data["name"]
                if npc_data["icon"]!="":
                    npc_icon_key = "leaderboard_class_"+npc_data["icon"]+".vtf"
                    npc_icon_path = f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}"
                    npc_png_icon_path = f"hud_images/{npc_data["icon"]}.png"
                    raw_npc_icon_path = f"./TF2-Zombie-Riot/dev_files_donot_use_for_server/hud_icons/WIP/RawClassIcons/leaderboard_class_{NPCS_BY_FILENAME[wave_entry_data["plugin"]]["icon"]}.png"
                    if os.path.isfile(npc_icon_path):
                        if not os.path.isfile(npc_png_icon_path):
                            npc_icon = vtf2img.Parser(f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}").get_image()
                            npc_icon.save(npc_png_icon_path)
                        image = f'<img src="{npc_png_icon_path}" alt="A" width="16"/>'
                    elif os.path.isfile(raw_npc_icon_path):
                        if not os.path.isfile(npc_png_icon_path):
                            os.rename(raw_npc_icon_path, npc_png_icon_path)
                        image = f'<img src="{npc_png_icon_path}" alt="B" width="16"/>'
                    elif not os.path.isfile(npc_png_icon_path): # if file doesn't exist already (in case of testing locally, where files aren't reset every time)
                        image = f'<img src="./hud_images/missing.png" alt="C" width="16"/>'
                else:
                    image = f'<img src="./hud_images/missing.png" alt="D" width="16"/>'
                MARKDOWN_WAVESETS += f"{count} {image} [{npc_name}](npcs.md#{wave_entry_data["plugin"]}){extra_info}  \n"
                if wave_entry_data["plugin"] not in added_npc_ids:
                    added_npc_ids.append(wave_entry_data["plugin"])
                    npc_health = f"Default health: {npc_data["health"]}  \n" if npc_data["health"] != "" else ""
                    MARKDOWN_NPCS += f"# {image.replace("16","32")} {npc_name}  \n###### {wave_entry_data["plugin"]}  \n{npc_health}{npc_data["description"]}  \n"
    
    # TODO: List of npcs by plugin name
    write("wavesets.md", MARKDOWN_WAVESETS)
    write("npcs.md", MARKDOWN_NPCS)

## COMPILE WEAPON CFG -------------------------------------------------------------------------------------------------


def compile_weapon():
    print("Compiling Weapon List...")
    MARKDOWN_WEAPON = ""
    CFG_WEAPONS = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/weapons.cfg"))["Weapons"]
    PHRASES_WEAPON = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.weapons.description.txt").replace("'\n",'"\n'))["Phrases"]
    
    def is_item_category(c):
        return "enhanceweapon_click" not in c and "cost" not in c


    def is_weapon(c):
        return "desc" in c or "author" in c


    def is_trophy(c):
        return "desc" in c and "visual_desc_only" in c


    def is_category(c):
        return "author" not in c and "filter" in c and "whiteout" not in c


    def interpret_weapon_paps(weapon_data):
        pap_idx = 0
        pap_md = ""
        pap_links = ""
        # TODO
        return pap_md, pap_links


    def parse_weapon_data(weapon_name, weapon_data, depth):
        if "tags" in weapon_data: tags = " ".join(f"#{tag}" for tag in weapon_data["tags"].split(";") if tag != "")
        else: tags = ""

        if "author" in weapon_data: author = f"Author: {weapon_data["author"]}"
        else: author = ""

        cost = "$" + weapon_data["cost"]

        if "desc" in weapon_data: 
            k = weapon_data["desc"]
            if k in PHRASES_WEAPON:
                description = f"{PHRASES_WEAPON[k]["en"].replace("\\n","\n")}\n"
            else: # this only exists because of the Infinity Blade
                description = k
        else: description = ""

        pap_md, pap_links = interpret_weapon_paps(weapon_data)
        
        return f"##{"#"*depth} {weapon_name}\n{tags}  \n{author}  \n{cost}  \n{description}  \n{pap_links}  "


    def item_block(key,data,depth,markdown):
        if "hidden" not in data:
            depth += 1
            markdown += f"#{"#"*depth} {key}\n"
            for item in data:
                item_data = data[item]
                if is_trophy(item_data):
                    markdown += f"Trophy: {item}\n"
                elif is_weapon(item_data):
                    markdown += parse_weapon_data(item,item_data,depth)
                elif item[0].isupper() and is_category(item_data) or "Perks" in item or "Trophies"==item: # unneeded data is always lowercase...
                    markdown = item_block(item, item_data, depth, markdown)
                elif "whiteout" in item_data:
                    markdown += f"Info: {item}\n"
        return markdown


    for item_category in CFG_WEAPONS:
        if is_item_category(CFG_WEAPONS[item_category]):
            MARKDOWN_WEAPON = item_block(item_category,CFG_WEAPONS[item_category],0,MARKDOWN_WEAPON)

    write("weapons.md", MARKDOWN_WEAPON)

compile_weapon()
compile_waveset_npc()