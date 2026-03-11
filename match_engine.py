# -*- coding: utf-8 -*-
"""
match_engine.py — IJF 2026 pure match logic (no GUI)
"""
import random, time
from dataclasses import dataclass, field
from typing import Optional, Callable

MATCH_DURATION   = 240
OSAEKOMI_IPPON   = 20
OSAEKOMI_WAZAARI = 10

@dataclass
class Score:
    ippon: int = 0
    wazaari: int = 0
    yuko: int = 0
    shido: int = 0
    hansokumake: bool = False
    def reset(self):
        self.ippon=0; self.wazaari=0; self.shido=0; self.hansokumake=False
        self.yuko=0

@dataclass
class MatchEvent:
    event_type: str
    side: str
    match_time: int = 0

class MatchEngine:
    def __init__(self, on_update: Optional[Callable]=None, match_duration: int=MATCH_DURATION,
                 allow_golden: bool = True):
        self.match_duration = match_duration
        self.on_update = on_update or (lambda: None)
        self.white_id: Optional[int] = None
        self.blue_id:  Optional[int] = None
        self.category: str = ""
        self.allow_golden = allow_golden
        self.stage = "FINAL"
        self._reset_state()

    def _reset_state(self):
        self.time_left = self.match_duration
        self.running = False
        self.golden  = False
        self.finished = False
        self.winner: Optional[str] = None
        self.white = Score()
        self.blue  = Score()
        self.osaekomi: Optional[str] = None
        self.osaekomi_elapsed = 0
        self.events: list = []

    # ── Timer ─────────────────────────────────────────────────────────────────
    def start(self):
        if not self.finished: self.running=True; self.on_update()
    def stop(self):
        self.running=False; self.on_update()
    def toggle(self):
        self.stop() if self.running else self.start()

    def tick(self):
        """Call every 1 second from QTimer."""
        if not self.running or self.finished: return
        if not self.golden:
            self.time_left = max(0, self.time_left-1)
            if self.time_left == 0:
                if self.allow_golden:
                    self.golden = True
                else:
                    self.running = False
                    self._resolve_deadlock()
        if self.osaekomi:
            self.osaekomi_elapsed += 1
            self._check_osaekomi()
        self._check_win()
        self.on_update()

    # ── Osaekomi ──────────────────────────────────────────────────────────────
    def start_osaekomi(self, side: str):
        if self.finished or self.osaekomi: return
        self.osaekomi = side; self.osaekomi_elapsed = 0
        if not self.running: self.start()
        else: self.on_update()

    def stop_osaekomi(self):
        self.osaekomi=None; self.osaekomi_elapsed=0; self.on_update()

    def _check_osaekomi(self):
        s = self.white if self.osaekomi=="white" else self.blue
        t = self.osaekomi_elapsed
        if t >= OSAEKOMI_IPPON:
            s.ippon=1; self._log("osaekomi_ippon", self.osaekomi); self.stop_osaekomi()
        elif t == OSAEKOMI_WAZAARI and s.wazaari==0:
            s.wazaari+=1; self._log("osaekomi_wazaari", self.osaekomi)

    # ── Scoring ───────────────────────────────────────────────────────────────
    def add_ippon(self, side):
        if self.finished: return
        s = self.white if side=="white" else self.blue
        s.ippon=1; self._log("ippon",side); self._check_win(); self.on_update()

    def add_wazaari(self, side):
        if self.finished: return
        s = self.white if side=="white" else self.blue
        s.wazaari+=1; self._log("wazaari",side); self._check_win(); self.on_update()

    def add_yuko(self, side):
        if self.finished: return
        s = self.white if side=="white" else self.blue
        s.yuko+=1; self._log("yuko", side); self._check_win(); self.on_update()

    def add_shido(self, side):
        if self.finished: return
        s = self.white if side=="white" else self.blue
        s.shido+=1
        if s.shido>=3: s.hansokumake=True
        self._log("shido",side); self._check_win(); self.on_update()

    def add_hansokumake(self, side):
        if self.finished: return
        s = self.white if side=="white" else self.blue
        s.hansokumake=True; self._log("hansokumake",side); self._check_win(); self.on_update()

    def remove_score(self, side, score_type):
        s = self.white if side=="white" else self.blue
        if score_type=="ippon"       and s.ippon>0:    s.ippon-=1
        elif score_type=="wazaari"   and s.wazaari>0:  s.wazaari-=1
        elif score_type=="yuko"      and s.yuko>0:     s.yuko-=1
        elif score_type=="shido"     and s.shido>0:
            s.shido-=1; s.hansokumake = s.shido>=3
        elif score_type=="hansokumake": s.hansokumake=False
        self.finished=False; self.winner=None; self.on_update()

    # ── Win detection ─────────────────────────────────────────────────────────
    def _check_win(self):
        if self.finished: return
        w,b = self.white, self.blue
        if w.hansokumake:        self._end("blue");  return
        if b.hansokumake:        self._end("white"); return
        if w.ippon>=1:           self._end("white"); return
        if b.ippon>=1:           self._end("blue");  return
        if w.wazaari>=2:         self._end("white"); return
        if b.wazaari>=2:         self._end("blue");  return
        if self.golden:
            if w.wazaari>0:      self._end("white"); return
            if b.wazaari>0:      self._end("blue");  return
            if w.shido>0 and b.shido==0: self._end("blue");  return
            if b.shido>0 and w.shido==0: self._end("white"); return

    def _compare_yuko(self):
        if self.white.yuko > self.blue.yuko:
            self._end("white"); return True
        if self.blue.yuko > self.white.yuko:
            self._end("blue"); return True
        return False

    def _resolve_deadlock(self):
        if self.finished: return
        if self._compare_yuko(): return
        w,b = self.white, self.blue
        if w.shido != b.shido:
            winner = "blue" if w.shido > b.shido else "white"
            self._end(winner); return
        self.finished = True
        self.running = False

    def _end(self, winner):
        self.winner=winner; self.finished=True
        self.running=False; self.osaekomi=None; self.on_update()

    def _log(self, etype, side):
        self.events.append(MatchEvent(etype, side, self.time_left))

    def set_stage(self, stage: str):
        self.stage = (stage or "").upper()

    def set_match_duration(self, seconds: int):
        if seconds <= 0: return
        self.match_duration = seconds
        self.time_left = min(self.time_left, seconds)

    def set_allow_golden(self, allow: bool):
        self.allow_golden = bool(allow)
        if not self.allow_golden:
            self.golden = False

    def reset(self, white_id=None, blue_id=None, category=None):
        if white_id is not None: self.white_id=white_id
        if blue_id  is not None: self.blue_id=blue_id
        if category is not None: self.category=category
        self._reset_state(); self.on_update()

    def time_str(self):
        t = self.time_left
        return f"{t//60:02d}:{t%60:02d}"

    def to_result_dict(self):
        return {
            "white_id": self.white_id, "blue_id": self.blue_id,
            "category": self.category, "winner": self.winner,
            "white_score": {"ippon":self.white.ippon,"wazaari":self.white.wazaari,
                            "shido":self.white.shido,"hansokumake":self.white.hansokumake,"yuko":self.white.yuko},
            "blue_score":  {"ippon":self.blue.ippon, "wazaari":self.blue.wazaari,
                            "shido":self.blue.shido, "hansokumake":self.blue.hansokumake,"yuko":self.blue.yuko},
            "golden_score": self.golden,
            "stage":        self.stage,
            "events": [{"type":e.event_type,"side":e.side,"time":e.match_time} for e in self.events],
        }

# ── Draw generation ───────────────────────────────────────────────────────────
def _next_power_of_two(n):
    size = 1
    while size < n:
        size *= 2
    return size

def _generate_bracket(pool, preserve_order=False):
    players = pool[:]
    if not preserve_order:
        random.shuffle(players)
    n = len(players)
    size = _next_power_of_two(n)
    pairs = size // 2

    # Seed so no pair is BYE vs BYE
    pair_slots = [[None, None] for _ in range(pairs)]
    # First pass: one athlete per pair
    first_count = min(pairs, len(players))
    for i in range(first_count):
        pair_slots[i][0] = players[i]
    # Second pass: fill second slot per pair
    remaining = players[first_count:]
    indices = list(range(pairs))
    random.shuffle(indices)
    idx = 0
    for p in remaining:
        while pair_slots[indices[idx]][1] is not None:
            idx = (idx + 1) % pairs
        pair_slots[indices[idx]][1] = p
        idx = (idx + 1) % pairs

    round0 = []
    for a, b in pair_slots:
        if a and b:
            round0.append({"white": a, "blue": b, "winner_id": None})
        else:
            player = a or b
            round0.append({"white": player, "blue": None, "winner_id": player["id"], "bye": True})

    rounds = [round0]
    length = len(round0)
    while length > 1:
        length = max(1, length // 2)
        rounds.append([None] * length)
    return rounds, size, n

def _round_robin_matches(players):
    matches = []
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            matches.append({"p1": players[i], "p2": players[j], "winner_id": None})
    return matches

def _path_opponents(rounds, player_id, include_semi=False):
    if not rounds:
        return []
    end = -1 if include_semi else -2
    if len(rounds) <= 1:
        return []
    if not include_semi and len(rounds) < 2:
        return []
    opponents = []
    for round_list in rounds[:end]:
        for match in round_list:
            if not match: continue
            w = match.get("white"); b = match.get("blue")
            if not w or not b: continue
            if w["id"] == player_id or b["id"] == player_id:
                if match.get("winner_id") == player_id:
                    opponents.append(b if w["id"] == player_id else w)
                break
    return opponents

def _semi_loser(rounds, player_id):
    if len(rounds) < 2: return None
    for match in rounds[-2]:
        if not match: continue
        w = match.get("white"); b = match.get("blue")
        if not w or not b: continue
        if w["id"] == player_id or b["id"] == player_id:
            if match.get("winner_id") == player_id:
                return b if w["id"] == player_id else w
            return None
    return None

def _build_repechage_side(defeated, semi_loser, mode):
    if not semi_loser:
        return None
    if mode == "double":
        pool = defeated[:]
        rounds, _, _ = _generate_bracket(pool, preserve_order=True)
        if rounds and rounds[-1]:
            for m in rounds[-1]:
                if m:
                    m["bronze"] = True
        return {"rounds": rounds}
    if not defeated:
        return None
    if len(defeated) == 1:
        return {"rounds": [[{"white": defeated[0], "blue": semi_loser, "winner_id": None, "bronze": True}]]}
    rounds, _, _ = _generate_bracket(defeated, preserve_order=True)
    rounds.append([{"white": None, "blue": semi_loser, "winner_id": None, "bronze": True}])
    return {"rounds": rounds}

def _advance_byes_in_rounds(rounds, players):
    for ri, round_list in enumerate(rounds[:-1]):
        for mi, match in enumerate(round_list):
            if not match: 
                continue
            if match.get("bye") and match.get("winner_id"):
                wid = match["winner_id"]
                slot = mi // 2
                first = mi % 2 == 0
                if slot >= len(rounds[ri+1]):
                    rounds[ri+1].extend([None] * (slot - len(rounds[ri+1]) + 1))
                if rounds[ri+1][slot] is None:
                    rounds[ri+1][slot] = {"white": None, "blue": None, "winner_id": None}
                player = next((p for p in players if p.get("id") == wid), None)
                if first:
                    rounds[ri+1][slot]["white"] = player
                else:
                    rounds[ri+1][slot]["blue"] = player

def _update_repechage(draw, players):
    if draw.get("type") != "bracket":
        draw["repechage"] = None
        return
    rounds = draw.get("rounds", [])
    if not rounds or len(rounds) < 2:
        draw["repechage"] = None
        return
    mode = draw.get("repechage_mode", "simple")

    def _loser(match):
        if not match: return None
        w = match.get("white"); b = match.get("blue")
        if not w or not b: return None
        wid = match.get("winner_id")
        if not wid: return None
        return b if w.get("id") == wid else w

    def _make_match(a, b, bronze=False):
        if a and b:
            return {"white": a, "blue": b, "winner_id": None, "bronze": bronze}
        player = a or b
        if not player:
            return {"white": None, "blue": None, "winner_id": None, "bye": True, "bronze": bronze}
        return {"white": player, "blue": None, "winner_id": player["id"], "bye": True, "bronze": bronze}

    if mode == "simple":
        final = rounds[-1][0] if rounds[-1] else None
        finalists = [final.get("white"), final.get("blue")] if final else [None, None]
        # For 8-player brackets use standard QF->SF structure
        if len(rounds) == 3:
            qf_round = rounds[-3]
            sf_round = rounds[-2]
            if len(qf_round) >= 4 and len(sf_round) >= 2:
                qf1_l = _loser(qf_round[0])
                qf2_l = _loser(qf_round[1])
                sf1_l = _loser(sf_round[0])
                sf2_l = _loser(sf_round[1])
                left = [_make_match(qf1_l, qf2_l, bronze=False),
                        _make_match(None, sf2_l, bronze=True)]
                qf3_l = _loser(qf_round[2])
                qf4_l = _loser(qf_round[3])
                right = [_make_match(qf3_l, qf4_l, bronze=False),
                         _make_match(None, sf1_l, bronze=True)]
                draw["repechage"] = {
                    "top": {"rounds": [[left[0]], [left[1]]]},
                    "bottom": {"rounds": [[right[0]], [right[1]]]},
                }
                return
        # For larger brackets, include all opponents who lost to finalists (excluding semi)
        if not finalists[0] or not finalists[1]:
            # Gradual repechage: build from current QF/SF data even before finals
            if len(rounds) >= 3:
                qf_round = rounds[-3]
                sf_round = rounds[-2]
                qf1_l = _loser(qf_round[0]) if len(qf_round) > 0 else None
                qf2_l = _loser(qf_round[1]) if len(qf_round) > 1 else None
                qf3_l = _loser(qf_round[2]) if len(qf_round) > 2 else None
                qf4_l = _loser(qf_round[3]) if len(qf_round) > 3 else None
                sf1_l = _loser(sf_round[0]) if len(sf_round) > 0 else None
                sf2_l = _loser(sf_round[1]) if len(sf_round) > 1 else None
                left = [_make_match(qf1_l, qf2_l, bronze=False),
                        _make_match(None, sf2_l, bronze=True)]
                right = [_make_match(qf3_l, qf4_l, bronze=False),
                         _make_match(None, sf1_l, bronze=True)]
                draw["repechage"] = {
                    "top": {"rounds": [[left[0]], [left[1]]]},
                    "bottom": {"rounds": [[right[0]], [right[1]]]},
                }
                return
            draw["repechage"] = {
                "top": {"rounds": [[_make_match(None, None, bronze=True)]]},
                "bottom": {"rounds": [[_make_match(None, None, bronze=True)]]},
            }
            return
        sides = {}
        for idx, finalist in enumerate(finalists):
            defeated = _path_opponents(rounds, finalist["id"], include_semi=False)
            semi_loser = _semi_loser(rounds, finalist["id"])
            rep_rounds, _, _ = _generate_bracket(defeated, preserve_order=True) if defeated else ([], 0, 0)
            if not rep_rounds:
                rep_rounds = [[]]
            rep_rounds.append([_make_match(None, semi_loser, bronze=True)])
            _advance_byes_in_rounds(rep_rounds, players)
            side_key = "top" if idx == 0 else "bottom"
            sides[side_key] = {"rounds": rep_rounds}
        draw["repechage"] = sides
        return

    if mode == "double" and len(rounds) >= 2:
        final = rounds[-1][0] if rounds[-1] else None
        finalists = [final.get("white"), final.get("blue")] if final else [None, None]
        if not finalists[0] or not finalists[1]:
            draw["repechage"] = {
                "top": {"rounds": [[_make_match(None, None, bronze=True)]]},
                "bottom": {"rounds": [[_make_match(None, None, bronze=True)]]},
            }
            return
        sf_round = rounds[-2]
        # Map finalist -> semi index and loser of each semi
        semi_losers = {}
        finalist_semi = {}
        for i, m in enumerate(sf_round):
            if not m: continue
            w = m.get("white"); b = m.get("blue"); wid = m.get("winner_id")
            if not w or not b or not wid: continue
            loser = b if w.get("id") == wid else w
            semi_losers[i] = loser
            finalist_semi[wid] = i
        sides = {}
        for idx, finalist in enumerate(finalists):
            if not finalist: 
                continue
            semi_idx = finalist_semi.get(finalist.get("id"))
            other_idx = 1 - semi_idx if semi_idx in (0,1) else None
            bronze_opponent = semi_losers.get(other_idx)
            defeated = _path_opponents(rounds, finalist["id"], include_semi=True)
            rep_rounds, _, _ = _generate_bracket(defeated, preserve_order=True)
            # Final bronze match against opposite semi loser
            rep_rounds.append([_make_match(None, bronze_opponent, bronze=True)])
            _advance_byes_in_rounds(rep_rounds, players)
            side_key = "top" if idx == 0 else "bottom"
            sides[side_key] = {"rounds": rep_rounds}
        draw["repechage"] = sides
        return

    sides = {}
    for idx, finalist in enumerate(finalists):
        include_semi = (mode == "double")
        defeated = _path_opponents(rounds, finalist["id"], include_semi=include_semi)
        semi_loser = _semi_loser(rounds, finalist["id"])
        side_key = "top" if idx == 0 else "bottom"
        sides[side_key] = _build_repechage_side(defeated, semi_loser, mode)
    draw["repechage"] = sides

def generate_draw(players, repechage_mode="simple"):
    pool = players[:]
    random.shuffle(pool)
    if len(pool) in (3, 5):
        return {
            "type": "round_robin",
            "players": pool,
            "matches": _round_robin_matches(pool),
            "repechage_mode": repechage_mode,
            "num_players": len(pool),
        }
    rounds, base, n = _generate_bracket(pool, preserve_order=False)
    draw = {
        "type": "bracket",
        "rounds": rounds,
        "repechage_mode": repechage_mode,
        "num_players": n,
        "size": base,
    }
    for mi, match in enumerate(rounds[0]):
        if match and match.get("bye") and match.get("winner_id"):
            advance_winner(draw, 0, mi, match["winner_id"], players)
    _update_repechage(draw, players)
    return draw

def advance_winner(draw, round_idx, match_idx, winner_id, players):
    if draw.get("type") == "round_robin":
        matches = draw.get("matches", [])
        if 0 <= match_idx < len(matches):
            matches[match_idx]["winner_id"] = winner_id
        return
    rounds = draw["rounds"]
    rounds[round_idx][match_idx]["winner_id"] = winner_id
    if round_idx + 1 < len(rounds):
        slot   = match_idx // 2
        first  = match_idx % 2 == 0
        player = next((p for p in players if p["id"] == winner_id), None)
        if slot >= len(rounds[round_idx+1]):
            rounds[round_idx+1].extend([None] * (slot - len(rounds[round_idx+1]) + 1))
        if rounds[round_idx+1][slot] is None:
            rounds[round_idx+1][slot] = {"white": None, "blue": None, "winner_id": None}
        if first: rounds[round_idx+1][slot]["white"] = player
        else:     rounds[round_idx+1][slot]["blue"]  = player
    _update_repechage(draw, players)

def advance_repechage(draw, side_key, round_idx, match_idx, winner_id, players):
    rep = draw.get("repechage") or {}
    side = rep.get(side_key) if isinstance(rep, dict) else None
    if not side:
        return
    rounds = side.get("rounds", [])
    if round_idx < 0 or round_idx >= len(rounds):
        return
    match = rounds[round_idx][match_idx]
    match["winner_id"] = winner_id
    if round_idx + 1 < len(rounds):
        slot = match_idx // 2
        first = match_idx % 2 == 0
        player = next((p for p in players if p["id"] == winner_id), None)
        if rounds[round_idx+1][slot] is None:
            rounds[round_idx+1][slot] = {"white": None, "blue": None, "winner_id": None}
        if first: rounds[round_idx+1][slot]["white"] = player
        else:     rounds[round_idx+1][slot]["blue"]  = player

def apply_result_to_draw(draw, white_id, blue_id, winner_id, players):
    if not draw or not winner_id:
        return False
    if draw.get("type") == "round_robin":
        matches = draw.get("matches", [])
        for i, m in enumerate(matches):
            p1 = m.get("p1"); p2 = m.get("p2")
            if not p1 or not p2: continue
            ids = {p1.get("id"), p2.get("id")}
            if ids == {white_id, blue_id}:
                m["winner_id"] = winner_id
                return True
        return False

    rounds = draw.get("rounds", [])
    for ri, round_list in enumerate(rounds):
        for mi, match in enumerate(round_list):
            if not match: continue
            w = match.get("white"); b = match.get("blue")
            if not w or not b: continue
            ids = {w.get("id"), b.get("id")}
            if ids == {white_id, blue_id}:
                advance_winner(draw, ri, mi, winner_id, players)
                return True
    return False
