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

let last_tag = "";
function remove_items_by_tag(root, tag) {
    last_tag = tag;
    const la = Array.prototype.slice.call(root.getElementsByTagName("li"),0);
    const lb = Array.prototype.slice.call(root.getElementsByTagName("div"),0);
    const l = la.concat(lb);
    let has_visible_items = false
    for (var i=0, item; item = l[i]; i++) {
        if (item.hasAttribute("weapon_tags")) {
            let attr = item.getAttribute("weapon_tags");
            if (!attr.includes(tag)) {
                item.classList.add("hidden");
            } else {
                if (!paps_shown && item.classList.contains("weapon_pap")) { continue }; //respect current pap filter
                item.classList.remove("hidden");
                has_visible_items = true;
            }
        }
    }
    if (!has_visible_items) {
        root.classList.add("hidden");
    } else {
        root.classList.remove("hidden");
    }
}

let paps_shown = false;
function togglePaps(checkbox) {
    paps_shown = checkbox.checked;
    const pap_elements = document.getElementsByClassName("weapon_pap");
    if (paps_shown) {
        for (var i=0, item; item = pap_elements[i]; i++) {
            if (!item.getAttribute("weapon_tags").includes(last_tag)) { continue }; //respect current tag filter
            item.classList.remove("hidden");
        }
    } else {
        for (var i=0, item; item = pap_elements[i]; i++) {
            item.classList.add("hidden");
        }
    }
}


/*
Custom right click modal
const all_items = document.getElementsByTagName("li");
let last_popup = null;
function show_popup(item) {
    if (last_popup!==null) { hide_popup(last_popup) };
    const pap_container = item.getElementsByClassName("tooltip_pap")[0];
    const item_container = item.getElementsByClassName("tooltip")[0];
    pap_container.classList.remove("hidden");
    item_container.classList.add("hidden");
    pap_container.style["top"] = "125%";
    last_popup = item;
}
function hide_popup(item) {
    const pap_container = item.getElementsByClassName("tooltip_pap")[0];
    const item_container = item.getElementsByClassName("tooltip")[0];
    pap_container.classList.add("hidden");
    item_container.classList.remove("hidden");
    pap_container.style["top"] = "110%";
}
for (var i=0, item; item = all_items[i]; i++) {
    item.addEventListener('contextmenu', function(e) {
        show_popup(e.target);
        e.preventDefault();
    }, false);
}
document.addEventListener('click', function(event) {
    if (last_popup!==null) {
        if (event.target !== last_popup) {
            hide_popup(last_popup);
        }
    }
});*/