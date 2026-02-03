# Parse all items, weapons and their paps.
import util
from keyvalues1 import KeyValues1

PHRASES_WEAPON = KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/translations/zombieriot.phrases.weapons.description.txt"))["Phrases"]
CFG_WEAPONS = KeyValues1.parse(util.read("./TF2-Zombie-Riot/addons/sourcemod/configs/zombie_riot/weapons.cfg"))["Weapons"]

class WeaponPap:
    def __init__(self, weapon_name, weapon_data, idx, depth):
        self.depth = depth
        pap_key = f"pap_{idx}_"
        key_desc = pap_key+"desc"
        if key_desc in weapon_data:
            key_customname = pap_key + "custom_name"
            if key_customname in weapon_data: self.name = weapon_data[key_customname]
            else: self.name = weapon_name
            
            self.description = weapon_data[key_desc]

            self.cost = weapon_data[pap_key+"cost"]

            if pap_key+"tags" in weapon_data: self.tags = " ".join(f"#{tag}" for tag in weapon_data[pap_key+"tags"].split(";") if tag != "")
            else: self.tags = ""

            # There has got to a better way to do this
            key_papskip = pap_key+"papskip"
            if key_papskip in weapon_data: self.papskip = weapon_data[key_papskip]
            else: self.papskip = "0"

            key_pappaths = pap_key+"pappaths"
            if key_pappaths in weapon_data: self.pappaths = weapon_data[key_pappaths]
            else: self.pappaths = "1"

            key_extra_desc = pap_key+"extra_desc"
            if key_extra_desc in weapon_data: self.extra_desc = weapon_data[key_extra_desc]
            else: self.extra_desc = ""

            self.attributes = weapon_data[pap_key+"attributes"]
            self.id = util.id_from_str(self.attributes)
        
        self.valid = key_desc in weapon_data


    def to_md(self):
        if self.description in PHRASES_WEAPON:
            desc = PHRASES_WEAPON[self.description]["en"]
        else:
            desc = self.description # some paps don't have translation for whatever reason lmao
        
        extra_desc = self.extra_desc if len(self.extra_desc) > 0 else ""

        space_header = " "*self.depth
        space = " "*round(self.depth*1.5) # Scale a bit to align with header spacing

        if len(self.tags)>0: tags = f"{space}{self.tags}  \n"
        else: tags = ""

        return f"### {space_header} {self.name} \\[{self.id}\\]  \n{tags}{space}${self.cost}  \n{space}{desc.replace("\\n",f"  \n{space}")}  \n{space}{extra_desc.replace("\\n",f"  \n{space}")}  \n"
    
    def to_link(self):
        return f"{" "*self.depth}[{self.name}](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/Weapon_Paps#{util.to_section_link(self.name,self.depth>0)}-{self.id})  \n"

class WeaponPap_Dummy:
    def __init__(self, init_pap_paths):
        self.papskip = "0"
        self.pappaths = init_pap_paths


def parse():
    util.log("Parsing Weapon List...")

    MARKDOWN_WEAPON = ""
    MARKDOWN_WEAPON_PAP = ""
    
    def is_item_category(c):
        return "enhanceweapon_click" not in c and "cost" not in c


    def is_weapon(c):
        return "desc" in c or "author" in c


    def is_trophy(c):
        return "desc" in c and "visual_desc_only" in c


    def is_category(c):
        return "author" not in c and "filter" in c and "whiteout" not in c

    def interpret_weapon_paps(weapon_name,weapon_data):
        """
        pap_#_pappaths define how many paps you can choose from below ("2" paths on "PaP 1" allows you to choose between "PaP 2" and "PaP 3")
        pap_#_papskip Skips a number of paps to choose ("1" skip on "PaP 1" allows you to choose "PaP 3" instead)
        """
        pap_idx = 0
        pap_md = ""
        pap_links = ""
        def item_block(parent_pap,idx,md,links,DEPTH):
            for i in range(int(parent_pap.pappaths)):
                idx += 1
                if int(parent_pap.pappaths)>1:
                    md += f"## {" "*DEPTH} _Path {i+1}_  \n"
                    links += f"{" "*DEPTH} _Path {i+1}_  \n"
                pd = WeaponPap(weapon_name,weapon_data,idx,DEPTH)
                if pd.valid:
                    md += pd.to_md()
                    links += pd.to_link()
                    if pd.pappaths!="0": md, links = item_block(pd, idx+int(pd.papskip), md, links,DEPTH+1)
            return md, links
        
        pap_md += f"# {weapon_name}  \n[Back to weapon](https://github.com/squarebracket-s/tf2_zr_wikigen/wiki/Items#{util.to_section_link(weapon_name)})  \n"
        if "pappaths" in weapon_data: init_pap_paths = weapon_data["pappaths"]
        else: init_pap_paths = 1
        pap_links = "**Paps**  \n"
        pap_md, pap_links = item_block(WeaponPap_Dummy(init_pap_paths), pap_idx, pap_md, pap_links, 0)
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


    tags = []
    for item_category in CFG_WEAPONS:
        if is_item_category(CFG_WEAPONS[item_category]):
            MARKDOWN_WEAPON, MARKDOWN_WEAPON_PAP, tags = item_block(item_category,CFG_WEAPONS[item_category],0,MARKDOWN_WEAPON,MARKDOWN_WEAPON_PAP, tags)
    
    taglist_str = "  \n".join({f" - #{tag}" for tag in tags})
    MARKDOWN_WEAPON = f"**Available tags:** \n{taglist_str}  \n"+MARKDOWN_WEAPON

    util.write("items.md", MARKDOWN_WEAPON)
    util.write("weapon_paps.md", MARKDOWN_WEAPON_PAP)
    return {
        "items.md": "Items.md",
        "weapon_paps.md": "Weapon_Paps.md"
    }