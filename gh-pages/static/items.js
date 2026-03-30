/* this may be extremely inefficient but hey it does the job */
function filter(tag) {
    const tags = document.getElementById("taglist").getElementsByTagName("div");
    for (var i=0, item; item = tags[i]; i++) {
        if (item.textContent.includes(tag)) {
            item.classList.add("btn-active");
        } else {
            item.classList.remove("btn-active");
        }
    }

    if (tag==="All") {tag=""};
    const r = document.getElementsByTagName("details");
    for (var i=0, item; item = r[i]; i++) {
        remove_items_by_tag(item, tag);
    }
}

function remove_items_by_tag(root, tag) {
    const l = root.getElementsByTagName("li")
    let has_visible_items = false
    if (l.length>0) {
        for (var i=0, item; item = l[i]; i++) {
            if (item.hasAttribute("weapon_tags")) {
                let attr = item.getAttribute("weapon_tags");
                if (!attr.includes(tag)) {
                    item.classList.add("hidden");
                } else {
                    item.classList.remove("hidden");
                    has_visible_items = true;
                }
            }
        }
    } else {
        const r = root.getElementsByTagName("details")
        for (var i=0, item; item = r[i]; i++) {
            if (remove_items_by_tag(item, tag)) {
                has_visible_items=true;
            }
        }
    }
    if (!has_visible_items) {
        root.classList.add("hidden");
    } else {
        root.classList.remove("hidden");
    }
    return has_visible_items
}