import hashlib, os, datetime

# https://stackoverflow.com/questions/3768895/how-to-make-a-class-json-serializable
# Allow classes to define __json__ to be JSON serializable
from json import JSONEncoder
def wrapped_default(self, obj):
    return getattr(obj.__class__, "__json__", wrapped_default.default)(obj)
wrapped_default.default = JSONEncoder().default
JSONEncoder.original_default = JSONEncoder.default
JSONEncoder.default = wrapped_default
###

CATEGORIES = []
if "DEBUG" in os.environ:
    CATEGORIES = [x.lower() for x in os.environ["DEBUG"].split(",")]


def id_from_str(string):
    # https://stackoverflow.com/questions/49808639/generate-a-variable-length-hash
    return hashlib.shake_256(string.encode("utf-8")).hexdigest(4)


def to_section_link(str_, pre_h=False):
    remove = [
        "&",
        "[",
        "]",
        "'",
        ","
    ]
    for r in remove:
        str_ = str_.replace(r,"")
    return f"{"-"*int(pre_h)}{str_.lower().replace(" ","-")}"


def md_img(url, alt, width=16):
    #return f'<img src="{url}" alt="{alt}" width="{width}"/>'
    return f'<img src="{url}" width="{width}"/>'


def normalize_whitespace(str_):
    return " ".join(str_.split())


def remove_multiline_comments(d): # Fixes the script interpreting the comment in npc_headcrabzombie.sp as actual data
    new_str = ""
    reading_comment = False
    for line in d.splitlines():
        if line == "/*": reading_comment=True
        if line == "*/": reading_comment=False
        if not reading_comment:
            new_str += line
    return new_str


def debug(str_, category, color="OKGREEN"):
    if category in CATEGORIES: log(str_,color)


# Logging
bcolors = {
    "HEADER": '\033[95m',
    "OKBLUE": '\033[94m',
    "OKCYAN": '\033[96m',
    "OKGREEN": '\033[92m',
    "WARNING": '\033[93m',
    "FAIL": '\033[91m',
    "ENDC": '\033[0m',
    "BOLD": '\033[1m',
    "UNDERLINE": '\033[4m'
}


pcolors = {
    "HEADER": (255,255,255),
    "OKBLUE": (12,109,240),
    "OKCYAN": (12,240,196),
    "OKGREEN": (53,240,12),
    "WARNING": (239,203,12),
    "FAIL": (255,0,0),
    "BOLD": (230,230,230),
    "UNDERLINE": (200,200,200)
}


def log(message, color="OKGREEN"):
    time = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
    pre = "[INFO] "
    if color == "WARNING": pre="[WARN] "
    if color == "FAIL": pre="[ERR] "
    if "OK" in color: pre="[LOG] "
    print(bcolors[color] + time + pre + message + bcolors["ENDC"])


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