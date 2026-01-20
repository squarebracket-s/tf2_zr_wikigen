import hashlib
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
