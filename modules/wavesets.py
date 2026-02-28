# Parse all NPCs & Wavesets (Normal & Custom, wavesets like Construction are yet to be supported.)
import util, os, pathlib, vtf2img, json
from collections import defaultdict
from keyvalues1 import KeyValues1
# https://stackoverflow.com/questions/2082152/how-to-make-a-case-insensitive-dictionary
from requests.structures import CaseInsensitiveDict

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
        #self.file_data = self.file_data.replace("	","")
        if ("npc_donoteveruse" not in self.file_data and "NPC_Add" in self.file_data):

            # Get NPC name
            # TODO multi-npc files can have different prefixes
            prefixes = [
                "data",
                "lantean_data",
                "data_buffed" # addons/sourcemod/scripting/zombie_riot/npc/bonezone/wave60/npc_necromancer.sp
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
                self.icon = self.file_data.split(f"strcopy({self.main_prefix}.Icon, sizeof({self.main_prefix}.Icon), \"")[1].split("\");")[0]
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
            self.name = self.file_data.split(f"strcopy({self.main_prefix}.Name, sizeof({self.main_prefix}.Name), \"")[1].split("\");")[0]
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
        self.plugin = self.file_data.split(f"strcopy({self.main_prefix}.Plugin, sizeof({self.main_prefix}.Plugin), \"")
        self.plugin = [item.split("\");")[0] for i,item in enumerate(self.plugin) if i > 0]

        self.category = self.file_data.split(f"{self.main_prefix}.Category = ")
        self.category = [item.split(";")[0] for i,item in enumerate(self.category) if i > 0]

        self.flags = self.file_data.split(f"{self.main_prefix}.Flags = ")
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
        self.plugin = self.file_data.split(f"strcopy({self.main_prefix}.Plugin, sizeof({self.main_prefix}.Plugin), \"")
        self.plugin = [item.split("\");")[0] for i,item in enumerate(self.plugin) if i > 0]

        self.category = self.file_data.split(f"{self.main_prefix}.Category = ")
        self.category = [item.split(";")[0] for i,item in enumerate(self.category) if i > 0]

        self.flags = self.file_data.split(f"{self.main_prefix}.Flags = ")
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
        self.plugin = self.file_data.split(f"strcopy({self.main_prefix}.Plugin, sizeof({self.main_prefix}.Plugin), \"")[1].split("\");")[0]

        try:
            self.category = self.file_data.split(f"{self.main_prefix}.Category = ")[1].split(";")[0]
        except IndexError:
            self.category = f"404 prefix: {self.main_prefix}"
        
        try:
            self.flags = self.file_data.split(f"{self.main_prefix}.Flags = ")[1]
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
                
waveset_cache = {}
def parse():
    generated_files = {
        "npcs.md": "NPCs.md",
        "home.md": "Home.md",
        "sidebar.md": "_Sidebar.md"
    }

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
    
    def add_npc(plugin, data):
        if plugin not in added_npc_ids:
            added_npc_ids.append(plugin)
            npc_data = NPCS_BY_FILENAME[plugin]
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
            return f"# {data["image"].replace("16","32")} {data["name"]}  \n_{plugin}_  \n{npc_health}{npc_flags}{npc_data.description}  \n"
        return ""

    def parse_wave(wave_data, md_npc, is_betting=False, force=False):
        md_new = ""
        for wave_entry in wave_data:
            wave_entry_data = wave_data[wave_entry]
            try:
                float(wave_entry)
            except ValueError:
                if wave_entry.startswith("music_"):
                    if (mdata := util.music_modal(wave_entry_data)): md_new += mdata
                
                if wave_entry == "xp":
                    md_new += f"Wave XP: {wave_entry_data}  \n"

                if wave_entry == "cash":
                    md_new += f"Wave cash: ${wave_entry_data}  \n"
                
                if wave_entry == "setup":
                    md_new += f"Setup time: {util.as_duration(wave_entry_data)}  \n"
                
                continue

            count = "always 1" if wave_entry_data["count"] == "0" else wave_entry_data["count"]
            budget = f"${int(float(wave_entry))} " if is_betting else "" # int("1.0") -> ValueError | int(float("1.0")) -> 1
            
            if wave_entry_data["plugin"] in NPCS_BY_FILENAME:
                npc_data = NPCS_BY_FILENAME[wave_entry_data["plugin"]]
            else:
                npc_data = None
                assert force

            try:
                npc_name = npc_data.name
            except AttributeError:
                npc_name = wave_entry_data["plugin"]
            npc_name_prefix = ""

            # Health data
            """
            bool carrier = data[0] == 'R';
            bool elite = !carrier && data[0];
            """
            extra_info = ""
            if "health" in wave_entry_data:
                extra_info += f" {wave_entry_data["health"]}HP"
            elif npc_data:
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
                        util.debug(f"Parsing HP Value {npc_data.health} DATA value {wave_entry_data["data"]} CHOSEN value {data_key}", "npc", "OKCYAN")
                        h = f" {npc_data.health[data_key.lower()]}"
                    else:
                        h = npc_data.health["default"]
                    extra_info += f" {h}HP"
                else:
                    extra_info += f" {npc_data.health}"
            else:
                extra_info += " ?HP"
            
            # Show NPC Flags
            # TODO some icons missing even tho they exist
            display_name = npc_name
            if npc_data:
                for flag in npc_data.flags:
                    if flag != "0" and flag != "-1":
                        extra_info += f" {FLAG_MAPPINGS[flag]}"

                # Get icon
                if npc_data.icon!="":
                    npc_icon_key = "leaderboard_class_"+npc_data.icon+".vtf"
                    npc_png_icon_path = f"repo_img/{npc_data.icon}.png"
                    
                    # Paths to look in for icons
                    npc_icon_path = f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}"
                    premedia_npc_icon_path = f"./premedia_icons/{npc_data.icon}.png"
                    if os.path.isfile(npc_icon_path):
                        if not os.path.isfile(npc_png_icon_path):
                            npc_icon = vtf2img.Parser(f"./TF2-Zombie-Riot/materials/hud/{npc_icon_key}").get_image()
                            npc_icon.save(npc_png_icon_path)
                        image = util.md_img(npc_png_icon_path,"A")
                    elif os.path.isfile(premedia_npc_icon_path):
                        image = util.md_img(premedia_npc_icon_path,"B")
                    else:
                        image = util.md_img("./builtin_img/missing.png","C")
                else:
                    image = util.md_img("./builtin_img/missing.png","D")
                
                if npc_data.category != "Type_Hidden":
                    display_name = util.to_file_link(npc_name,"NPCs",npc_name,True)
                    # Add NPC if not hidden & doesn't exist already
                    md_npc += add_npc(wave_entry_data["plugin"], {"name": npc_name, "image": image}) 
            else:
                image = util.md_img("./builtin_img/missing.png","E")
                

                
            
            # Show if NPC is scaled
            if "force_scaling" in wave_entry_data:
                if wave_entry_data["force_scaling"]=="1":
                    extra_info += " _(forcibly scaled)_"

            # Add NPC to wave data   
            md_new += f"{budget} {count} {image} {npc_name_prefix} {display_name} {extra_info}  \n"
        
        return md_new, md_npc
    
    def parse_waveset(name, data, md_wavesets, md_npc):
        global waveset_cache
        if name in waveset_cache:
            util.debug(f"    -> Returning cache for {name}", "waveset", "OKCYAN")
            md_wavesets += waveset_cache[name]
            return md_wavesets, md_npc
        
        wd = defaultdict(str,data)
        md_new = ""
        a_npc = f"NPCs by: {wd["author_npcs"]}  \n" if wd["author_npcs"] != "" else ""
        a_format = f"Format by: {wd["author_format"]}  \n" if wd["author_format"] != "" else ""
        a_raid = f"Raidboss by: {wd["author_raid"]}  \n" if wd["author_raid"] != "" else ""
        complete_item = f"Item on win: {wd["complete_item"]}  \n" if wd["complete_item"] != "" else ""
        md_new += f"{a_npc}{a_format}{a_raid}{complete_item}"
        
        wave_idx = 0
        for wave in data:
            wave_data = data[wave]
            try:
                int(wave)
            except ValueError:
                if wave.startswith("music_"):
                    if (mdata := util.music_modal(wave_data)): md_new += mdata
                continue

            wave_npc_amt = sum([int(util.is_float(entry)) for entry in wave_data])
            if len(wave_data)==0 or wave_npc_amt == 0: continue
            wave_idx += 1

            abovelimit = False if "fakemaxwaves" not in wd else wave_idx > int(wd["fakemaxwaves"]) # If wave number is above specified max fake limit

            mn, md_npc = parse_wave(wave_data, md_npc)
            md_new += f"## {wave_idx}  \n{mn}" # marking in headers does not work in github markdown!! TODO
        
        waveset_cache[name] = md_new
        md_wavesets += md_new
        return md_wavesets, md_npc
    
    def parse_betting(name, data, md_npc, md_mapsets):
        wd = defaultdict(str,data)
        betting_music = util.music_modal(data["Betting"]["BetWars"]["music_background"])
        mn, md_npc = parse_wave(data["Betting"]["Waves"]["Freeplay"], md_npc, is_betting=True, force=True)

        n = name.split("/")[-1].replace(".cfg","")
        md_mapsets += f"- [{n}]({n})  \n"
        
        return f"{betting_music}\n  {mn}", md_npc, md_mapsets
    
    def parse_waveset_list_cfg_common(cfg, filename, md_npc, md_mapsets):
        map_mode = "Custom" in cfg # Is map specific config?
        WAVESET_LIST = cfg[list(cfg.keys())[0]] # data of cfg file
        if "Setup" in WAVESET_LIST: WAVESET_LIST = WAVESET_LIST["Setup"] # map-specific configs start with custom instead of setup, requiring an extra step to get to waveset/wave< data

        MARKDOWN_WAVESETS = f"Starting cash: ${WAVESET_LIST["cash"]}  \n"
        
        if "Waves" in WAVESET_LIST: # list of wavesets
            wavesets = WAVESET_LIST["Waves"]
            # Outline
            if len(wavesets)>1:
                MARKDOWN_WAVESETS += "# Wavesets  \n"
                for waveset_name in wavesets:
                    MARKDOWN_WAVESETS += f"- [{waveset_name}](#{util.to_section_link(waveset_name)})  \n"

            # Modifier outline
            if "Modifiers" in WAVESET_LIST:
                MARKDOWN_WAVESETS += f"# Modifiers  \n"
                for modifiers in WAVESET_LIST["Modifiers"]:
                    MARKDOWN_WAVESETS += f"- [{modifiers}](#{util.to_section_link(modifiers)})  \n"    
            
            # Data
            for waveset_name in wavesets:
                waveset_file = wavesets[waveset_name]["file"]
                util.log(f"    {waveset_name}{" "*(35-len(waveset_name))}| {waveset_file}")
                wave_cfg = util.read(f"./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/{waveset_file}.cfg")
                # Waveset-specific typo fixes (or just removing lines that break the parser)
                if waveset_file == "classic_iber&expi": wave_cfg=wave_cfg.replace('			"plugin"	"110000000"',"") # overrides actual plugin name before it, which is why it has to be removed
                wave_cfg = unique_enemy_delays(wave_cfg)

                WAVESET_DATA = KeyValues1.parse(wave_cfg)["Waves"]

                if "desc" in wavesets[waveset_name]:
                    waveset_desc_key = wavesets[waveset_name]["desc"]
                    if waveset_desc_key in PHRASES_WAVESET:
                        desc = PHRASES_WAVESET[waveset_desc_key]["en"].replace("\\n","  \n")
                    else:
                        desc = waveset_desc_key.replace("\\n","  \n") # Blame Artvin PR #895 for not translating a desc
                else:
                    desc = ""
                MARKDOWN_WAVESETS += f"# {waveset_name}  \n{"[Back to top](#wavesets)  \n" * int(not map_mode)}{desc}  \n"

                MARKDOWN_WAVESETS, md_npc = parse_waveset(waveset_file, WAVESET_DATA, MARKDOWN_WAVESETS, md_npc)
        else: # Waveset itself / map_mode | Assume data being in the cfg file itself. See: maps/zr_bossrush.cfg
            # mapset, i.e. only one waveset
            # also add link to its config file in md_mapsets (mapset outline in home.md and sidebar.md)
            MARKDOWN_WAVESETS, md_npc = parse_waveset(filename, WAVESET_LIST, MARKDOWN_WAVESETS, md_npc)
        
        if map_mode: 
            n = filename.split("/")[-1].replace(".cfg","")
            md_mapsets += f"- [{n}]({n})  \n"
        
        # Modifiers title and desc
        if "Modifiers" in WAVESET_LIST:
            for modifier in WAVESET_LIST["Modifiers"]:
                data = WAVESET_LIST["Modifiers"][modifier]
                desc = PHRASES_NPC_2[data["desc"]]["en"].replace("\\n","  \n")
                MARKDOWN_WAVESETS += f"# {modifier}  \n[Back to top](#modifiers)  \nMinimum level: {float(data["level"])*1000}  \n{desc}  \n"
        
        return MARKDOWN_WAVESETS, md_npc, md_mapsets

    def parse_waveset_list_cfg(filename, md_npc, md_mapsets):
        WAVESETLIST_DATA = KeyValues1.parse(util.read(f"./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/{filename}"))
        WAVESETLIST_TYPE = list(WAVESETLIST_DATA.keys())[0]

        if WAVESETLIST_TYPE not in ["Setup", "Custom", "Betting"]: # Unsupported waveset cfg (Rogue, Bunker, etc.)
            util.log(f"Unsupported waveset cfg {filename}!","WARNING")
            return md_npc, md_mapsets
        
        util.log(f"Parsing waveset list cfg: {filename}")

        """
        Special waveset support:
        - [x] Betting

        Unlikely:
        - [ ] Rogue
        - [ ] Construction
        - [ ] Dungeon

        maps/zr_bunker_old_fish.cfg - currently disabled in zr and has missing files
        maps/zr_beastrooms.cfg - empty
        maps/zr_integratedstrategies.cfg - rogue
        maps/zr_deepforest.cfg - rogue
        maps/zr_construction.cfg - construction
        maps/zr_const2_headquarters.cfg - dungeon
        maps/zr_bettingwars.cfg - betting/freeplay: delay defines budget/describes how powerful the NPCs are
        maps/zr_holdout.cfg - construction
        maps/zr_rift_between_fates.cfg - rogue
        """

        if WAVESETLIST_TYPE in ["Setup", "Custom"]:
            # TODO global MARKDOWN_WAVESETS
            MARKDOWN_WAVESETS, md_npc, md_mapsets = parse_waveset_list_cfg_common(WAVESETLIST_DATA, filename, md_npc, md_mapsets)
        elif WAVESETLIST_TYPE == "Betting":
            MARKDOWN_WAVESETS, md_npc, md_mapsets = parse_betting(filename, WAVESETLIST_DATA, md_npc, md_mapsets)
        else:
            MARKDOWN_WAVESETS = f"err key {WAVESETLIST_TYPE}"

        if WAVESETLIST_TYPE in ["Custom", "Betting"]:
            filename_md = filename.split("/")[-1].replace(".cfg","") + ".md"
            display_name = filename_md
        else:
            filename_md = f"wavesets_{filename}.md".replace("/","_")
            disp = filename.replace(".cfg","").replace("_"," ").replace("/"," ")
            disp_title = disp.replace("'","~").title().replace("~","'") # https://stackoverflow.com/a/1549644
            display_name = f"{disp_title}.md"
        
        generated_files[filename_md] = display_name
        util.write(filename_md, MARKDOWN_WAVESETS)
        return md_npc, md_mapsets

    # NPC list is global to prevent duplicates
    PATH_NPC = "./TF2-Zombie-Riot/addons/sourcemod/scripting/zombie_riot/npc/"
    # TODO what the hell. make this global
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