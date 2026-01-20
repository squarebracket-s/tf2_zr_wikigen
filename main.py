import os
from keyvalues1 import KeyValues1
import vtf2img
import re

import util

# Utility functions
# U+3164 -> 'ㅤ'
# also ' '
WIKI_FILES = {
    "items.md": "Items.md",
    "weapon_paps.md": "Weapon_Paps.md",
    "npcs.md": "NPCs.md",
    "skilltree.md": "Skilltree.md"
}

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
    def extract_npc_data(path):
        file_data = read(path)
        file_data = remove_multiline_comments(file_data)
        if ("npc_donoteveruse" not in file_data and "NPC_Add" in file_data):
            # Get name
            name = file_data.split("	strcopy(data.Name, sizeof(data.Name), \"")[1].split("\");")[0]
            
            # Get plugin and health
            # TODO: Case for non-shared file with multiple NPC_Add calls (-> different npc names) Example: raidmode_bosses/npc_god_alaxios.sp (sea-infected god alaxios isn't present in any redsun cfg!)
            if "shared" in path:
                plugin = file_data.split("	strcopy(data.Plugin, sizeof(data.Plugin), \"")
                plugin = [item.split("\");")[0] for i,item in enumerate(plugin) if i > 0]

                category = file_data.split("	data.Category = ")
                category = [item.split(";")[0] for i,item in enumerate(category) if i > 0]

                base_path = path.replace(path.split("/")[-1],"") # remove deepest item
                health = []
                for i,p in enumerate(plugin):
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

                try:
                    category = file_data.split("	data.Category = ")[1].split(";")[0]
                except IndexError:
                    category = ""

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
            return True, {"name": name, "category": category,"description": description, "plugin": plugin, "icon": icon, "health": health}
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
                        pn_data["health"] = pn_data["health"][min(len(pn_data["health"])-1,i)]
                        pn_data["category"] = pn_data["category"][min(len(pn_data["category"])-1,i)]
                        pn_data["plugin"] = pn_data["plugin"][min(len(pn_data["plugin"])-1,i)]
                        npc_by_file[pn] = pn_data
                else:                    
                    npc_by_file[plugin_name] = data[npc_file]

        if "DEBUG" in os.environ:
            try:
                if bool(os.environ["DEBUG"]):
                    import json
                    write("npc_data.json",json.dumps(npc_by_file,indent=2))
            except ValueError:
                print("DEBUG env couldn't be converted to bool!")
        return npc_by_file
    

    def unique_enemy_delays(w):
        # Make each wave delay unique as not to lose out on info (for example if 2 enemies have same wave delay)
        # https://stackoverflow.com/questions/41941116/replace-each-occurrence-of-sub-strings-in-the-string-with-randomly-generated-val
        space = "		"
        for i in range(0,301):
            delay_str = f'{i/10:.1f}'
            delay_count = w.count(delay_str)
            w = w.replace("{","{{").replace("}","}}").replace(f'{space}"{delay_str}"', space+'"{}"')
            w = w.format(*(" "*i + delay_str for i in range(delay_count)))
        return w
    

    def parse_waveset_list_cfg(cfg, md_npc):
        print(f"Parsing waveset list cfg: {cfg}")
        MARKDOWN_WAVESETS = "# Outline  \n"
        WAVESET_LIST = KeyValues1.parse(read(f"./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/{cfg}"))["Setup"]    
        for waveset_name in WAVESET_LIST["Waves"]:
            MARKDOWN_WAVESETS += f"- [{waveset_name}](#{util.to_section_link(waveset_name)})  \n"
    
        for waveset_name in WAVESET_LIST["Waves"]:
            waveset_file = WAVESET_LIST["Waves"][waveset_name]["file"]
            print(f"    Parsing waveset: {waveset_name} Filename: {waveset_file}")
            wave_cfg = read(f"./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/{waveset_file}.cfg")
            # Waveset-specific typo fixes (or just removing lines that break the parser)
            if waveset_file == "classic_iber&expi": wave_cfg=wave_cfg.replace('			"plugin"	"110000000"',"") # overrides actual plugin name before it, which is why it has to be removed
            wave_cfg = unique_enemy_delays(wave_cfg)
            WAVESET_DATA = KeyValues1.parse(wave_cfg)["Waves"]

            waveset_desc_key = WAVESET_LIST["Waves"][waveset_name]["desc"]
            MARKDOWN_WAVESETS += f"# {waveset_name}  \n[Back to Outline](#outline)  \n{PHRASES_WAVESET[waveset_desc_key]["en"].replace("\\n","  \n")}  \n"
            
            for wave in WAVESET_DATA:
                try:
                    int(wave) # Check if key can be converted to a number to detect wave notation
                except ValueError:
                    continue
                MARKDOWN_WAVESETS += f"## {wave}  \n"
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
                        npc_png_icon_path = f"hud_images/{npc_data["icon"]}.png"
                        
                        # Paths to look in for icons
                        npc_icon_path = f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}"
                        raw_npc_icon_path = f"./TF2-Zombie-Riot/dev_files_donot_use_for_server/hud_icons/WIP/RawClassIcons/leaderboard_class_{npc_data["icon"]}.png"
                        if os.path.isfile(npc_icon_path):
                            if not os.path.isfile(npc_png_icon_path):
                                npc_icon = vtf2img.Parser(f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}").get_image()
                                npc_icon.save(npc_png_icon_path)
                            image = f'<img src="{npc_png_icon_path}" alt="A" width="16"/>'
                        elif os.path.isfile(raw_npc_icon_path):
                            if not os.path.isfile(npc_png_icon_path): # Local testing has persistent env
                                os.rename(raw_npc_icon_path, npc_png_icon_path)
                            image = f'<img src="{npc_png_icon_path}" alt="B" width="16"/>'
                        elif os.path.isfile(npc_png_icon_path): # Local testing has persistent env
                            image = f'<img src="{npc_png_icon_path}" alt="B" width="16"/>'
                        else:
                            image = f'<img src="./hud_images/missing.png" alt="C" width="16"/>'
                    else:
                        image = f'<img src="./hud_images/missing.png" alt="D" width="16"/>'
                    if npc_data["category"] != "Type_Hidden":
                        MARKDOWN_WAVESETS += f"{count} {image} [{npc_name}](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/NPCs#{"-"+npc_name.lower().replace(" ","-").replace(",","")}) {extra_info}  \n"
                        if wave_entry_data["plugin"] not in added_npc_ids:
                            added_npc_ids.append(wave_entry_data["plugin"])
                            npc_health = f"Default health: {npc_data["health"]}  \n" if npc_data["health"] != "" else ""
                            npc_cat = f"Category: {npc_data["category"]}  \n" if npc_data["category"] != "" else ""
                            md_npc += f"# {image.replace("16","32")} {npc_name}  \n_{wave_entry_data["plugin"]}_  \n{npc_health}{npc_cat}{npc_data["description"]}  \n"
                    else:
                        MARKDOWN_WAVESETS += f"{count} {image} {npc_name} {extra_info}  \n"

        filename = f"wavesets_{cfg}.md"
        display_name = f"Wavesets {cfg.replace(".cfg","").capitalize()}.md"
        WIKI_FILES[filename] = display_name
        write(filename, MARKDOWN_WAVESETS)
        return md_npc

    # TODO: Map-specific wavesets such as Matrix (stored in addons/sourcemod/zombie_riot/config/maps/)
    # NPC list is global to prevent duplicates
    PATH_NPC = "./TF2-Zombie-Riot/addons/sourcemod/scripting/zombie_riot/npc/"
    MARKDOWN_NPCS = ""
    added_npc_ids = []

    PHRASES_NPC = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.zombienames.txt"))["Phrases"]
    PHRASES_NPC_2 = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.item.gift.desc.txt"))["Phrases"]
    PHRASES_WAVESET = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.txt"))["Phrases"]

    print("Parsing NPCs...")
    NPCS_BY_FILENAME = parse_all_npcs()

    cfg_files = [
        "classic.cfg",
        "fastmode_redsun.cfg", 
    #    "fastmode.cfg", # normal fastmode not included since modifiers aren't shown yet
    ]
    for f in cfg_files:
        MARKDOWN_NPCS = parse_waveset_list_cfg(f, MARKDOWN_NPCS)

    write("npcs.md", MARKDOWN_NPCS)

## COMPILE WEAPON CFG -------------------------------------------------------------------------------------------------

def compile_weapon():
    print("Compiling Weapon List...")
    MARKDOWN_WEAPON = ""
    MARKDOWN_WEAPON_PAP = ""
    CFG_WEAPONS = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/weapons.cfg"))["Weapons"]
    PHRASES_WEAPON = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.weapons.description.txt"))["Phrases"]
    
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

            key_papskip = pap_key+"papskip"
            if key_papskip in weapon_data: pap_skip = weapon_data[key_papskip]
            else: pap_skip = "0"

            key_pappaths = pap_key+"pappaths"
            if key_pappaths in weapon_data: pap_paths = weapon_data[key_pappaths]
            else: pap_paths = "1"

            pap_attributes = weapon_data[pap_key+"attributes"]

            return {"name": pap_name, "description": pap_desc, "cost": pap_cost, "tags": pap_tags, "_skip": pap_skip, "_paths": pap_paths, "_attributes": pap_attributes}
        return None
    
    def pap_data_to_md(data,depth):
        if data["description"] in PHRASES_WEAPON:
            desc = PHRASES_WEAPON[data["description"]]["en"]
        else:
            desc = data["description"] # some paps don't have translation for whatever reason lmao
        space_header = " "*depth
        space = " "*round(depth*1.5) # Scale a bit to align with header spacing
        return f"### {space_header} {data["name"]} \\[{util.id_from_str(data["_attributes"])}\\]  \n{space if len(data["tags"])>0 else ""}{data["tags"]}{"  \n" if len(data["tags"])>0 else ""}{space}${data["cost"]}  \n{space}{desc.replace("\\n",f"  \n{space}")}  \n"

    def pap_data_to_link(data):
        return f"[{data["name"]}](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/Weapon_Paps#{util.to_section_link(data["name"],True)}-{util.id_from_str(data["_attributes"])})  \n"


    def interpret_weapon_paps(weapon_name,weapon_data):
        # TODO: Implement pap_#_extra_desc
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


    def parse_weapon_data(weapon_name, weapon_data, depth):
        if "tags" in weapon_data: tags = " ".join(f"#{tag}" for tag in weapon_data["tags"].split(";") if tag != "")
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
        
        return f"##{"#"*depth} {weapon_name}  \n{tags}  \n{author}  \n{cost}  \n{description}  \n{pap_links}  ", pap_md


    def item_block(key,data,depth,markdown,markdown_pap):
        if "hidden" not in data:
            depth += 1
            markdown += f"#{"#"*depth} {key}  \n"
            for item in data:
                item_data = data[item]
                if is_trophy(item_data):
                    markdown += f"Trophy: {item}  \n"
                elif is_weapon(item_data):
                    m1, m2 = parse_weapon_data(item,item_data,depth)
                    markdown += m1
                    markdown_pap += m2
                elif item[0].isupper() and is_category(item_data) or "Perks" in item or "Trophies"==item: # unneeded data is always lowercase...
                    markdown, markdown_pap = item_block(item, item_data, depth, markdown, markdown_pap)
                elif "whiteout" in item_data:
                    markdown += f"Info: {item}  \n"
        return markdown, markdown_pap


    for item_category in CFG_WEAPONS:
        if is_item_category(CFG_WEAPONS[item_category]):
            MARKDOWN_WEAPON, MARKDOWN_WEAPON_PAP = item_block(item_category,CFG_WEAPONS[item_category],0,MARKDOWN_WEAPON,MARKDOWN_WEAPON_PAP)

    write("items.md", MARKDOWN_WEAPON)
    write("weapon_paps.md", MARKDOWN_WEAPON_PAP)

## COMPILE SKILLTREE CFG -------------------------------------------------------------------------------------------------

def compile_skilltree():
    print("Compiling Skilltree...")
    """
    	"name"		"Luck Up 1"	// Name
        "player"	"SkillPlayer_LuckUp"	// Function
    //	"weapon"	"Tree_LuckUp"	// Functio	n
        "max"	"5"	// Max Charges	
        "cost"	"1"	// Point Cos	t
    //	"min"	"-1"	// Charge Required from Paren	t
    //	"key"	""	// Inventory Item Required
    """
    SKILLTREE_CFG = KeyValues1.parse(read("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/skilltree.cfg"))
    # strange formatting of the string I know
    MARKDOWN_SKILLTREE = """## Legend
- MIN: Minimum amount of ranks needed in parent skill to unlock  
- MAX: Maximum rank  
- COST: Amount of points needed per rank  
- REQ: Required item to unlock skill

```mermaid
    %%{init:{'theme':'dark'}}%%
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
    write("skilltree.md", MARKDOWN_SKILLTREE)

compile_weapon()
compile_waveset_npc()
compile_skilltree()

# Move files to wiki
if os.path.isdir("tf2_zr_wikigen.wiki/"):
    for file in WIKI_FILES:
        if os.path.isfile(file):
            os.rename(file, f"tf2_zr_wikigen.wiki/{WIKI_FILES[file]}")
        else:
            print(f"Missing file {file}: cannot move into wiki")