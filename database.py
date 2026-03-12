# -*- coding: utf-8 -*-
"""
database.py — File-system JSON database
Data stored in: ~/JudoManager/
"""
import json, os, shutil, re
from datetime import datetime

DATA_DIR      = os.path.join(os.path.expanduser("~"), "JudoManager")
PLAYERS_FILE  = os.path.join(DATA_DIR, "players.json")
DRAWS_FILE    = os.path.join(DATA_DIR, "draws.json")
MATCHES_FILE  = os.path.join(DATA_DIR, "matches.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "event_name":        "Judo Championship",
    "match_duration":    240,
    "osaekomi_ippon":    20,
    "osaekomi_wazaari":  10,
    "golden_score":      True,
    "age_group":         "Senior",
    "custom_weight_categories": "",
    "repechage_mode":    "simple",
    "custom_category_label": "Custom",
    "champions_by_category": {},
}

SAMPLE_PLAYERS = [

]

WEIGHT_CATEGORIES = {
    "male":   ["-60kg","-66kg","-73kg","-81kg","-90kg","-100kg","+100kg"],
    "female": ["-48kg","-52kg","-57kg","-63kg","-70kg","-78kg", "+78kg"],
}

AGE_GROUP_CATEGORIES = {
    "Senior": {
        "male":   ["-60kg","-66kg","-73kg","-81kg","-90kg","-100kg","+100kg"],
        "female": ["-48kg","-52kg","-57kg","-63kg","-70kg","-78kg","+78kg"],
    },
    "Junior": {
        "male":   ["-60kg","-66kg","-73kg","-81kg","-90kg","-100kg","+100kg"],
        "female": ["-48kg","-52kg","-57kg","-63kg","-70kg","-78kg","+78kg"],
    },
    "Cadet": {
        "male":   ["-55kg","-60kg","-66kg","-73kg","-81kg","-90kg","+90kg"],
        "female": ["-44kg","-48kg","-52kg","-57kg","-63kg","-70kg","+70kg"],
    },
}

def get_age_group_weights(age_group: str, gender: str):
    if age_group == "Custom":
        return []
    group = AGE_GROUP_CATEGORIES.get(age_group, AGE_GROUP_CATEGORIES["Senior"])
    return group.get(gender, [])

def parse_custom_weights(text: str):
    if not text:
        return []
    return [c.strip() for c in re.split(r"[,\n]+", text) if c.strip()]

def combined_weights(age_group: str, gender: str, custom_text: str):
    extras = parse_custom_weights(custom_text)
    if age_group == "Custom":
        return extras
    base = get_age_group_weights(age_group, gender)
    return base + extras

def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)

def _read(path, default):
    _ensure()
    if not os.path.exists(path): return default
    try:
        with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except: return default

def _write(path, data):
    _ensure()
    tmp = path + ".tmp"
    with open(tmp,"w",encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
    shutil.move(tmp, path)

# ── Players ───────────────────────────────────────────────────────────────────
def load_players():          return _read(PLAYERS_FILE, [])
def save_players(players):   _write(PLAYERS_FILE, players)

def add_player(p):
    players = load_players()
    p["id"] = max((x["id"] for x in players), default=0) + 1
    p["created_at"] = datetime.now().isoformat()
    players.append(p); save_players(players); return p

def update_player(pid, updates):
    players = load_players()
    for i,p in enumerate(players):
        if p["id"]==pid:
            players[i].update(updates)
            players[i]["updated_at"] = datetime.now().isoformat()
            save_players(players); return True
    return False

def delete_player(pid):
    players = load_players()
    new = [p for p in players if p["id"]!=pid]
    if len(new)==len(players): return False
    save_players(new); return True

def get_player(pid):
    for p in load_players():
        if p["id"]==pid: return p
    return None

def get_players_by_category(gender, weight):
    return [p for p in load_players()
            if p.get("gender")==gender and p.get("weight")==weight]

# ── Draws ─────────────────────────────────────────────────────────────────────
def load_draws():                        return _read(DRAWS_FILE, {})
def save_draws(d):                       _write(DRAWS_FILE, d)
def get_draw(key):                       return load_draws().get(key)
def set_draw(key, data):
    d=load_draws(); d[key]=data; d[key]["updated_at"]=datetime.now().isoformat(); save_draws(d)
def delete_draw(key):
    d=load_draws()
    if key in d: del d[key]; save_draws(d)

# ── Match history ─────────────────────────────────────────────────────────────
def load_matches():          return _read(MATCHES_FILE, [])
def save_match_result(r):
    m=load_matches(); r["saved_at"]=datetime.now().isoformat(); m.append(r); _write(MATCHES_FILE,m)
def clear_match_history():
    _write(MATCHES_FILE, [])

# ── Settings ──────────────────────────────────────────────────────────────────
def load_settings():
    return {**DEFAULT_SETTINGS, **_read(SETTINGS_FILE, {})}
def save_settings(s):        _write(SETTINGS_FILE, s)
def get_data_dir():          return DATA_DIR

def ensure_sample_players():
    """Add sample players if DB is empty."""
    if not load_players():
        for p in SAMPLE_PLAYERS:
            add_player(dict(p))
