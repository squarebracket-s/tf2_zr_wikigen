let wave = 1;
let max_waves = 40; // TODO apply fake max_waves
let waveset = "";
let waveset_file = null;
let waveset_data = {};
const npc_html = `<div class="wave_npc">
    npcimg
    <div class="wave_npc_count">npccount</div>

    <div class="tooltip">
        npcdata
    </div>
</div>`
function cycle_wave(val) {
    wave = wave + val;
    if (wave>max_waves) {wave=max_waves};
    if (wave<1) {wave=1};
    update_wave_display();
}

function set_wave(val) {
    let as_number = Number(val.replace(/\D/g,""));
    if (as_number>max_waves) {as_number=max_waves};
    if (as_number<1) {as_number=1};
    wave = as_number;
    update_wave_display();
}

async function parse_waveset(file) {
    waveset_file = "wavesets/"+file;
    try {
        const response = await fetch(waveset_file);
        if (!response.ok) {
            throw new Error(`Response status: ${response.status}`);
        }

        waveset_data = await response.json();
        console.log("Fetched "+waveset_file);
        update_wave_display();
    } catch (error) {
        console.error(error.message);
    }
}

function update_wave_display() {
    const wave_text = document.getElementById("wave_progress_text").getElementsByTagName("input")[0];
    const wave_bar = document.getElementById("wave_progress_bar").getElementsByTagName("div")[0];
    wave_text.value = wave;
    wave_bar.style.width = (wave/max_waves)*100 + "%";

    if (wave===max_waves) {
        wave_bar.style["border-radius"] = "5px"; 
    } else {
        wave_bar.style["border-radius"] = "5px 0px 0px 5px";
    }

    removeElementsByClass("wave_npc");

    const container = document.getElementById("npc_container");
    waveset_data["waves"][String(wave)].forEach(function (npc, _) {
        const context = {
            "npcimg": npc["img"],
            "npccount": npc["count"],
            "npcdata": "<h2>" + npc["prefix"] + npc["display_name"] + "</h2>" + npc["extra_info"]
        }
        container.innerHTML += fill_template(npc_html, context);
    });
}

let paramString = window.location.href.split('?')[1];
let queryString = new URLSearchParams(paramString);
for (let pair of queryString.entries()) {
    if (pair[0]=="w") { parse_waveset(pair[1]) };
    if (pair[0]=="wv") { set_wave(pair[1]) };
}


function fill_template(temp, cont) {
    for (let pair of Object.entries(cont)) {
        temp = temp.replace(pair[0],pair[1]);
    }
    return temp
}

// https://stackoverflow.com/questions/4777077/removing-elements-by-class-name
// I was too lazy :P
function removeElementsByClass(className){
    const elements = document.getElementsByClassName(className);
    while(elements.length > 0){
        elements[0].parentNode.removeChild(elements[0]);
    }
}