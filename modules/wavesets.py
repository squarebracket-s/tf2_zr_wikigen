# Parse all NPCs & Wavesets (Normal & Custom, wavesets like Construction are yet to be supported.)
import util, os, pathlib, vtf2img, json
from collections import defaultdict
from keyvalues1 import KeyValues1
# https://stackoverflow.com/questions/2082152/how-to-make-a-case-insensitive-dictionary
from requests.structures import CaseInsensitiveDict

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


PHRASES_NPC = CaseInsensitiveDict(KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.zombienames.txt"))["Phrases"])
PHRASES_NPC_2 = CaseInsensitiveDict(KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.item.gift.desc.txt"))["Phrases"])
PHRASES_WAVESET = CaseInsensitiveDict(KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.txt"))["Phrases"])

class NPC:
    def __init__(self, path):
        self.path=path
        util.debug(f"Init NPC {self.path}", "npc", "OKCYAN")
        self.file_data = util.read(self.path)
        self.file_data = util.remove_multiline_comments(self.file_data)
        if ("npc_donoteveruse" not in self.file_data and "NPC_Add" in self.file_data):

            # Get NPC name
            prefixes = [
                "data",
                "lantean_data"
            ]
            self.name = None
            for prefix in prefixes:
                if self.name is None: 
                    self.main_prefix = prefix
                    self._get_name()
            assert self.name is not None
            
            # Get plugin, category, flags, health
            if "shared" in self.path:
                self._set_npc_data_shared()
            if self.file_data.count("NPC_Add") > 1:
                self._set_npc_data_multi()
            else:
                self._set_npc_data_single()

            # Get icon
            try:
                self.icon = self.file_data.split(f"	strcopy({self.main_prefix}.Icon, sizeof({self.main_prefix}.Icon), \"")[1].split("\");")[0]
            except IndexError:
                self.icon = ""

            
            desc_key = f"{self.name} Desc"
            if desc_key in PHRASES_NPC:
                self.description = PHRASES_NPC[desc_key]["en"].replace("\\n","  \n")
            elif desc_key in PHRASES_NPC_2:
                self.description = PHRASES_NPC_2[desc_key]["en"].replace("\\n","  \n")
            else:
                self.description = ""
            
            """
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
            """

        self.hidden = not ("npc_donoteveruse" not in self.file_data and "NPC_Add" in self.file_data)

    def _get_name(self):
        try:
            self.name = self.file_data.split(f"	strcopy({self.main_prefix}.Name, sizeof({self.main_prefix}.Name), \"")[1].split("\");")[0]
        except IndexError:
            self.name = None
    

    def _parse_health_number(self, num):
        try:
            float(num)
            return num
        except ValueError:
            # Assume variable
            npc_vars = self.file_data.split("#define ")
            npc_vars_dict = {}
            for i, item in enumerate(npc_vars):
                if i > 0:
                    # May parse whole blocks of code as key&value pairs sometimes, but it gets the job done. Doesn't break actual variables in any way
                    full_str = item.split('"')
                    k, v = util.normalize_whitespace(full_str[0]).replace(" ",""), full_str[1].replace(" ","")
                    npc_vars_dict[k] = v

            if num in npc_vars_dict:
                util.debug(f"[X] {self.path} var {num}", "npc")
                return npc_vars_dict[num]
            else:
                util.debug(f"[ ] {self.path} var {num}", "npc")
                return "dynamic"
    
    def _set_npc_data_shared(self):
        # Several instances of NPC entry data, several instances of CClotBody in separate files
        self.plugin = self.file_data.split(f"	strcopy({self.main_prefix}.Plugin, sizeof({self.main_prefix}.Plugin), \"")
        self.plugin = [item.split("\");")[0] for i,item in enumerate(self.plugin) if i > 0]

        self.category = self.file_data.split(f"	{self.main_prefix}.Category = ")
        self.category = [item.split(";")[0] for i,item in enumerate(self.category) if i > 0]

        self.flags = self.file_data.split(f"	{self.main_prefix}.Flags = ")
        self.flags = [item.split(";")[0].split("|") for i,item in enumerate(self.flags) if i > 0]

        base_path = self.path.replace(self.path.split("/")[-1],"") # remove deepest item
        self.health = []
        for i,p in enumerate(self.plugin):
            p_data = util.read(base_path+p+".sp")
            try:
                h = self.file_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
                if "MinibossHealthScaling" in h:
                    h = f"Miniboss health scaling (Base {h.split("(")[1][:-1]}HP)"
                elif ":" in h:
                    """
                    extra "data" fields for enemies (lists, numbers or types like "Elite")
                    'data[0]?x' is probably checking if any value from the waveset cfg exists at all to use x? 
                    """
                    cases = h.split(":(")
                    if len(cases) == 0: cases = h.split(":")
                    h = {}
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
                                h[k] = self._parse_health_number(v)
                        else:
                            k,v = parse_case(case)
                            h[k] = self._parse_health_number(v)
                else:
                    h = self._parse_health_number(health) + "HP"
            except IndexError:
                h = "?"
            self.health.append(h)
    
    def _set_npc_data_multi(self):
        # Several instances of NPC entry data, one instance of CClotBody
        self.plugin = self.file_data.split(f"	strcopy({self.main_prefix}.Plugin, sizeof({self.main_prefix}.Plugin), \"")
        self.plugin = [item.split("\");")[0] for i,item in enumerate(self.plugin) if i > 0]

        self.category = self.file_data.split(f"	{self.main_prefix}.Category = ")
        self.category = [item.split(";")[0] for i,item in enumerate(self.category) if i > 0]

        self.flags = self.file_data.split(f"	{self.main_prefix}.Flags = ")
        self.flags = [item.split(";")[0].split("|") for i,item in enumerate(self.flags) if i > 0]
    
        try:
            self.health = self.file_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
            if "MinibossHealthScaling" in self.health:
                self.health = f"Miniboss health scaling (Base {self.health.split("(")[1][:-1]}HP)"
            elif ":" in self.health:
                """
                extra "data" fields for enemies (lists, numbers or types like "Elite")
                'data[0]?x' is probably checking if any value from the waveset cfg exists at all to use x? 
                """
                cases = self.health.split(":(")
                if len(cases) == 0: cases = self.health.split(":")
                self.health = {}
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
                            self.health[k] = self._parse_health_number(v)
                    else:
                        k,v = parse_case(case)
                        self.health[k] = self._parse_health_number(v)
            else:
                self.health = self._parse_health_number(self.health) + "HP"
        except IndexError:
            self.health = "?"
        self.filetype = "multi"
    
    def _set_npc_data_single(self):
        # One instance of everything
        self.plugin = self.file_data.split(f"	strcopy({self.main_prefix}.Plugin, sizeof({self.main_prefix}.Plugin), \"")[1].split("\");")[0]

        try:
            self.category = self.file_data.split(f"	{self.main_prefix}.Category = ")[1].split(";")[0]
        except IndexError:
            self.category = ""
        
        try:
            self.flags = self.file_data.split(f"	{self.main_prefix}.Flags = ")[1]
            self.flags = self.flags.split(";")[0].split("|")
        except IndexError:
            self.flags = []
        
        try:
            self.health = self.file_data.split("CClotBody(vecPos, vecAng, ")[1].split("));")[0].split(',')[2].replace('"',"").replace(" ","")
            if "MinibossHealthScaling" in self.health:
                self.health = f"Miniboss health scaling (Base {self.health.split("(")[1][:-1]}HP)"
            elif ":" in self.health:
                """
                extra "data" fields for enemies (lists, numbers or types like "Elite")
                'data[0]?x' is probably checking if any value from the waveset cfg exists at all to use x? 
                """
                cases = self.health.split(":(")
                if len(cases) == 0: cases = self.health.split(":")
                self.health = {}
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
                            self.health[k] = self._parse_health_number(v)
                    else:
                        k,v = parse_case(case)
                        self.health[k] = self._parse_health_number(v)
            else:
                self.health = self._parse_health_number(self.health) + "HP"
        except IndexError:
            self.health = "?"
        
        self.filetype = "single"
    
    def __json__(self):
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description, 
            "plugin": self.plugin, 
            "icon": self.icon, 
            "health": self.health, 
            "flags": self.flags,
            "filetype": self.filetype
        }

class NPC_Dummy:
    def __init__(self, npc_obj: NPC):
        # yes this is stupid. I won't change it.
        self.name = npc_obj.name
        self.icon = npc_obj.icon
        self.description = npc_obj.description
        self.filetype = npc_obj.filetype
    
    def __json__(self):
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description, 
            "plugin": self.plugin, 
            "icon": self.icon, 
            "health": self.health, 
            "flags": self.flags,
            "filetype": self.filetype
        }
                

def parse():
    generated_files = {}

    def parse_all_npcs():
        npc_by_file = {}
        for file in pathlib.Path(PATH_NPC).glob('**/*'):
            if os.path.isfile(file.absolute()):
                npc_obj = NPC(str(file.absolute()))
                if not npc_obj.hidden:
                    plugin_name = npc_obj.plugin
                    if type(plugin_name) == list:
                        for i,pn in enumerate(plugin_name):
                            dummy = NPC_Dummy(npc_obj)
                            if npc_obj.filetype == "shared":
                                dummy.health = npc_obj.health[min(len(npc_obj.health)-1,i)]
                            else:
                                dummy.health = npc_obj.health
                            dummy.category = npc_obj.category[min(len(npc_obj.category)-1,i)]
                            dummy.plugin = npc_obj.plugin[min(len(npc_obj.plugin)-1,i)]
                            dummy.flags = npc_obj.flags[min(len(npc_obj.flags)-1,i)]
                            npc_by_file[pn] = dummy
                    else:                    
                        npc_by_file[plugin_name] = npc_obj

        if "npc" in util.CATEGORIES:
            util.write("npc_data.json",json.dumps(npc_by_file,indent=2))

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
            md_mapsets += f"- [{n}]({n})  \n"
        
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
                MARKDOWN_WAVESETS += f"# {waveset_name}  \n{"[Back to top](#wavesets)  \n" * int(not map_mode)}{desc}  \n"
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
                        wave_data = defaultdict(str,wave_data)
                        music_case = wave.split("_")[1].capitalize()
                        name = wave_data["file"].replace("#","")
                        if wave_data["name"] != "": name = wave_data["name"]
                        if wave_data["author"] != "": author = f"by {wave_data["author"]}"
                        else: author = ""
                        music = f"{name} {author}"
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

                    npc_name = npc_data.name
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
                        if type(npc_data.health) == dict:
                            if "data" in wave_entry_data:
                                data_key = wave_entry_data["data"]
                                # vars
                                carrier = data_key[0] == "R"
                                elite = (not carrier) and data_key[0] # If first char isn't R but data exists

                                if carrier: data_key = "carrier"
                                elif elite: data_key = "elite"
                                else: data_key = "default";npc_name_prefix="!c"

                                if data_key not in npc_data.health and "any" in npc_data.health: data_key = "any";
                                elif data_key not in npc_data.health: data_key = "default";

                                npc_name_prefix += wave_entry_data["data"].capitalize()
                                util.debug(f"Parsing HP Value{npc_data.health} DATA value {wave_entry_data["data"]} CHOSEN value {data_key}", "OKCYAN")
                                h = f" {npc_data.health[data_key.lower()]}"
                            else:
                                h = npc_data.health["default"]
                            extra_info += f" {h}HP"
                        else:
                            extra_info += f" {npc_data.health}"
                    
                    # Show NPC Flags
                    for flag in npc_data.flags:
                        if flag != "0" and flag != "-1":
                            extra_info += f" {FLAG_MAPPINGS[flag]}"
                    
                    # Show if NPC is scaled
                    if "force_scaling" in wave_entry_data:
                        if wave_entry_data["force_scaling"]=="1":
                            extra_info += " _(forcibly scaled)_"
                    

                    # Get icon
                    if npc_data.icon!="":
                        npc_icon_key = "leaderboard_class_"+npc_data.icon+".vtf"
                        npc_png_icon_path = f"repo_img/{npc_data.icon}.png"
                        
                        # Paths to look in for icons
                        npc_icon_path = f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}"
                        raw_npc_icon_path = f"./TF2-Zombie-Riot/dev_files_donot_use_for_server/hud_icons/WIP/RawClassIcons/leaderboard_class_{npc_data.icon}.png"
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
                    if npc_data.category != "Type_Hidden":
                        MARKDOWN_WAVESETS += f"{count} {image} {npc_name_prefix} [{npc_name}](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/NPCs#{"-"+npc_name.lower().replace(" ","-").replace(",","")}) {extra_info}  \n"
                        # Add NPC if not hidden & doesn't exist already
                        if wave_entry_data["plugin"] not in added_npc_ids:
                            added_npc_ids.append(wave_entry_data["plugin"])
                            if type(npc_data.health) == dict:
                                npc_health = ""
                                for k,v in npc_data.health.items():
                                    npc_health += f"{k.capitalize()}: {v}HP"
                            else:
                                npc_health = f"Default health: {npc_data.health}  \n" if npc_data.health != "" else ""
                            npc_cat = f"Category: {npc_data.category}  \n" if npc_data.category != "" else ""
                            if "0" not in npc_data.flags and "-1" not in npc_data.flags:
                                npc_flags = "Flags: "
                                dflags = ", ".join([FLAG_MAPPINGS[item] for item in npc_data.flags])
                                npc_flags += dflags + "  \n"
                            else:
                                npc_flags = ""
                            md_npc += f"# {image.replace("16","32")} {npc_name}  \n_{wave_entry_data["plugin"]}_  \n{npc_health}{npc_flags.replace("\n"," ")}{npc_data.description.replace("\n"," ")}  \n"
                    else:
                        MARKDOWN_WAVESETS += f"{count} {image} {npc_name} {extra_info}  \n"

            if self_destruct: break

        if "Modifiers" in WAVESET_LIST:
            for modifier in WAVESET_LIST["Modifiers"]:
                data = WAVESET_LIST["Modifiers"][modifier]
                desc = PHRASES_NPC_2[data["desc"]]["en"].replace("\\n","  \n")
                MARKDOWN_WAVESETS += f"# {modifier}  \n[Back to top](#modifiers)  \nMinimum level: {float(data["level"])*1000}  \n{desc}  \n"

        if map_mode:
            filename = cfg.split("/")[-1].replace(".cfg","") + ".md"
            display_name = filename
        else:
            filename = f"wavesets_{cfg}.md".replace("/","_")
            disp = cfg.replace(".cfg","").replace("_"," ").replace("/"," ")
            disp_title = disp.replace("'","~").title().replace("~","'") # https://stackoverflow.com/a/1549644
            display_name = f"{disp_title}.md"
        generated_files[filename] = display_name
        util.write(filename, MARKDOWN_WAVESETS)
        return md_npc, md_mapsets

    # TODO: Map-specific wavesets such as Matrix (stored in addons/sourcemod/zombie_riot/config/maps/)
    # NPC list is global to prevent duplicates
    PATH_NPC = "./TF2-Zombie-Riot/addons/sourcemod/scripting/zombie_riot/npc/"
    MARKDOWN_NPCS = ""
    MARKDOWN_MAPSETS = "\n**Map-specific wavesets**  \n"
    added_npc_ids = []

    if not os.path.isdir("repo_img"): os.system("mkdir repo_img")

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
    return generated_files