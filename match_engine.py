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
        self.golden_elapsed = 0
        self.finished = False
        self.winner: Optional[str] = None
        self.white = Score()
        self.blue  = Score()
        self.osaekomi: Optional[str] = None
        self.osaekomi_elapsed = 0
        self.osaekomi_paused = False
        self.osaekomi_awarded_yuko = False
        self.osaekomi_awarded_wazaari = False
        self.events: list = []
        # Real-time tracking (prevents timer drift when the UI/event loop is busy).
        self._last_tick_mono: Optional[float] = None
        self._tick_accum: float = 0.0

    # ── Timer ─────────────────────────────────────────────────────────────────
    def start(self):
        if self.finished:
            return
        self.running = True
        self._last_tick_mono = time.monotonic()
        self._tick_accum = 0.0
        self.on_update()
    def stop(self):
        self.running = False
        self._last_tick_mono = None
        self._tick_accum = 0.0
        self.on_update()
    def toggle(self):
        self.stop() if self.running else self.start()

    def sono_mama(self):
        """Sono-mama: pause both match timer and osaekomi."""
        if not self.running or self.finished:
            return
        self.stop()
        if self.osaekomi:
            self.osaekomi_paused = True
        self.on_update()

    def yoshi(self):
        """Yoshi: resume both match timer and osaekomi."""
        if self.finished:
            return
        self.start()
        if self.osaekomi:
            self.osaekomi_paused = False
        self.on_update()

    def _step_one_second(self):
        if not self.golden:
            self.time_left = max(0, self.time_left-1)
            if self.time_left == 0:
                if self.allow_golden:
                    self.golden = True
                    self.golden_elapsed = 0
                else:
                    self.running = False
                    self._resolve_deadlock()
        else:
            self.golden_elapsed += 1
        
        # Osaekomi is now handled smoothly in tick()
        self._check_win()

    def tick(self):
        """Advance match time based on real elapsed time (robust to UI lag)."""
        if not self.running or self.finished:
            return
        now = time.monotonic()
        if self._last_tick_mono is None:
            self._last_tick_mono = now
            return
        dt = now - self._last_tick_mono
        self._last_tick_mono = now
        if dt <= 0:
            return

        # Smoothly update osaekomi to avoid "stepping" lag
        if self.osaekomi and not self.osaekomi_paused:
            self.osaekomi_elapsed += dt
            self._check_osaekomi()

        # Avoid unbounded catch-up loops if the app was suspended.
        self._tick_accum = min(self._tick_accum + dt, 3600.0)
        steps = int(self._tick_accum)
        if steps <= 0:
            # If osaekomi is running, we still want to update the UI for the smooth bar
            if self.osaekomi: self.on_update()
            return
        self._tick_accum -= steps
        for _ in range(steps):
            if not self.running or self.finished:
                break
            self._step_one_second()
        self.on_update()

    # ── Osaekomi ──────────────────────────────────────────────────────────────
    def start_osaekomi(self, side: str):
        if self.finished or self.osaekomi: return
        self.osaekomi = side; self.osaekomi_elapsed = 0
        self.osaekomi_paused = False
        self.osaekomi_awarded_yuko = False
        self.osaekomi_awarded_wazaari = False
        if not self.running: self.start()
        else: self.on_update()

    def stop_osaekomi(self):
        if not self.osaekomi:
            return
        self.osaekomi=None; self.osaekomi_elapsed=0
        self.osaekomi_paused = False
        self.osaekomi_awarded_yuko = False
        self.osaekomi_awarded_wazaari = False
        self.on_update()

    def pause_osaekomi(self):
        if not self.osaekomi:
            return
        self.osaekomi_paused = True
        self.on_update()

    def resume_osaekomi(self):
        if not self.osaekomi:
            return
        self.osaekomi_paused = False
        self.on_update()

    def _check_osaekomi(self):
        s = self.white if self.osaekomi=="white" else self.blue
        t = self.osaekomi_elapsed
        if t >= OSAEKOMI_IPPON:
            s.ippon=1; self._log("osaekomi_ippon", self.osaekomi)
            self.osaekomi=None; self.osaekomi_elapsed=0
            self.osaekomi_awarded_yuko = False
            self.osaekomi_awarded_wazaari = False
            self._check_win()
        elif t >= 10 and not self.osaekomi_awarded_wazaari:
            if self.osaekomi_awarded_yuko and s.yuko > 0:
                s.yuko -= 1
            s.wazaari += 1
            self.osaekomi_awarded_wazaari = True
            self._log("osaekomi_wazaari", self.osaekomi)
            self._check_win()
        elif t >= 5 and not self.osaekomi_awarded_yuko:
            s.yuko += 1
            self.osaekomi_awarded_yuko = True
            self._log("osaekomi_yuko", self.osaekomi)

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
            if w.yuko>0:         self._end("white"); return
            if b.yuko>0:         self._end("blue");  return
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
        if self.white.wazaari != self.blue.wazaari:
            self._end("white" if self.white.wazaari > self.blue.wazaari else "blue"); return
        if self._compare_yuko(): return
        w,b = self.white, self.blue
        if w.shido != b.shido:
            winner = "blue" if w.shido > b.shido else "white"
            self._end(winner); return
        self.finished = True
        self.running = False

    def _end(self, winner):
        self.winner=winner; self.finished=True
        self.running=False; self.osaekomi=None

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
        t = self.golden_elapsed if self.golden else self.time_left
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

def _seed_positions(size):
    raw = [
        0,
        size // 2,
        size // 4,
        3 * size // 4,
        size // 8,
        3 * size // 8,
        5 * size // 8,
        7 * size // 8,
    ]
    positions = []
    for p in raw:
        if 0 <= p < size and p not in positions:
            positions.append(p)
    return positions

def _generate_bracket(pool, preserve_order=False, champion_ids=None):
    players = pool[:]
    n = len(players)
    size = _next_power_of_two(n)
    pairs = size // 2

    # Seed champions in fixed bracket positions (max 8)
    seeds = []
    if champion_ids and not preserve_order:
        by_id = {p.get("id"): p for p in players}
        for cid in champion_ids:
            p = by_id.get(cid)
            if p and p not in seeds:
                seeds.append(p)
    if seeds:
        players = [p for p in players if p not in seeds]

    if not preserve_order:
        random.shuffle(players)

    pair_slots = [[None, None] for _ in range(pairs)]
    champ_pairs = []
    if seeds:
        positions = _seed_positions(size)
        for p, pos in zip(seeds, positions):
            pair = pos // 2
            slot = pos % 2
            if pair_slots[pair][slot] is None:
                pair_slots[pair][slot] = p
            else:
                for alt in positions:
                    ai = alt // 2
                    aj = alt % 2
                    if pair_slots[ai][aj] is None:
                        pair_slots[ai][aj] = p
                        pair, slot = ai, aj
                        break
            champ_pairs.append((p.get("id"), pair, slot))

    remaining = players[:]
    empty_pairs = [i for i, ps in enumerate(pair_slots) if ps[0] is None and ps[1] is None]
    random.shuffle(empty_pairs)

    # Fill empty pairs first (randomized) to distribute non-bye matches
    for i in empty_pairs:
        if not remaining:
            break
        pair_slots[i][0] = remaining.pop(0)
    for i in empty_pairs:
        if not remaining:
            break
        if pair_slots[i][1] is None:
            pair_slots[i][1] = remaining.pop(0)

    # If byes are limited, give them to lower-ranked champions first
    for _, pair, slot in reversed(champ_pairs):
        if not remaining:
            break
        opp = 1 - slot
        if pair_slots[pair][opp] is None:
            pair_slots[pair][opp] = remaining.pop(0)

    # Fill any remaining empty slots (fallback)
    for i in range(pairs):
        for s in (0, 1):
            if not remaining:
                break
            if pair_slots[i][s] is None:
                pair_slots[i][s] = remaining.pop(0)
        if not remaining:
            break

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
    # Circle method to distribute matches so athletes don't play back-to-back
    plist = players[:]
    random.shuffle(plist)
    if len(plist) % 2 == 1:
        plist.append(None)
    n = len(plist)
    rounds = []
    for _ in range(n - 1):
        round_matches = []
        for i in range(n // 2):
            a = plist[i]
            b = plist[n - 1 - i]
            if a is not None and b is not None:
                round_matches.append({"p1": a, "p2": b, "winner_id": None})
        rounds.append(round_matches)
        plist = [plist[0]] + [plist[-1]] + plist[1:-1]
    # Flatten rounds
    return [m for rnd in rounds for m in rnd]

def _pool_order(players, matches):
    ids = [p.get("id") for p in players if p and p.get("id") is not None]
    wins = {pid: 0 for pid in ids}
    for m in matches:
        wid = m.get("winner_id")
        if wid in wins:
            wins[wid] += 1
    # Stable order: wins desc, then id asc
    ordered_ids = sorted(ids, key=lambda pid: (-wins.get(pid, 0), pid))
    by_id = {p.get("id"): p for p in players if p}
    return [by_id.get(pid) for pid in ordered_ids if pid in by_id]

def _update_pool5(draw, players):
    pools = draw.get("pools", {})
    pool_a = pools.get("A", {})
    pool_b = pools.get("B", {})
    a_players = pool_a.get("players", [])
    b_players = pool_b.get("players", [])
    a_matches = pool_a.get("matches", [])
    b_matches = pool_b.get("matches", [])

    def _pool_complete(matches):
        for m in matches:
            p1 = m.get("p1"); p2 = m.get("p2")
            if p1 and p2 and not m.get("winner_id"):
                return False
        return True

    a_complete = _pool_complete(a_matches)
    b_complete = _pool_complete(b_matches)
    a_order = _pool_order(a_players, a_matches) if a_complete else []
    b_order = _pool_order(b_players, b_matches) if b_complete else []

    semis = draw.get("semis", [])
    while len(semis) < 2:
        semis.append({"white": None, "blue": None, "winner_id": None})
    draw["semis"] = semis

    def _set_match(match, white, blue):
        prev_w = match.get("white"); prev_b = match.get("blue")
        prev_ids = {prev_w.get("id") if prev_w else None, prev_b.get("id") if prev_b else None}
        new_ids = {white.get("id") if white else None, blue.get("id") if blue else None}
        if prev_ids != new_ids:
            match["winner_id"] = None
        match["white"] = white
        match["blue"] = blue

    if a_complete and b_complete:
        a1 = a_order[0] if len(a_order) > 0 else None
        a2 = a_order[1] if len(a_order) > 1 else None
        b1 = b_order[0] if len(b_order) > 0 else None
        b2 = b_order[1] if len(b_order) > 1 else None
        _set_match(semis[0], a1, b2)
        _set_match(semis[1], a2, b1)

    final = draw.get("final") or {"white": None, "blue": None, "winner_id": None}
    # Clear invalid winners
    for sm in semis:
        w = sm.get("white")
        b = sm.get("blue")
        if not w or not b:
            continue
        valid_ids = {w.get("id"), b.get("id")}
        if sm.get("winner_id") not in valid_ids:
            sm["winner_id"] = None
    # Advance to final
    w1 = semis[0].get("winner_id")
    w2 = semis[1].get("winner_id")
    if w1 and w2:
        p1 = next((p for p in players if p.get("id") == w1), None)
        p2 = next((p for p in players if p.get("id") == w2), None)
        prev_final_ids = {final.get("white", {}).get("id") if final.get("white") else None,
                          final.get("blue", {}).get("id") if final.get("blue") else None}
        new_final_ids = {p1.get("id") if p1 else None, p2.get("id") if p2 else None}
        if prev_final_ids != new_final_ids:
            final["winner_id"] = None
        final["white"] = p1
        final["blue"] = p2
        draw["final"] = final

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
                    rounds[ri+1][slot]["white_from"] = mi
                else:
                    rounds[ri+1][slot]["blue"] = player
                    rounds[ri+1][slot]["blue_from"] = mi

def _update_repechage(draw, players):
    if draw.get("type") != "bracket":
        draw["repechage"] = None
        return
    prev_rep = draw.get("repechage")
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

    def _ensure_bronze_match(side_rounds):
        if not side_rounds:
            side_rounds.append([{"white": None, "blue": None, "winner_id": None, "bronze": True}])
        elif not side_rounds[-1]:
            side_rounds[-1] = [{"white": None, "blue": None, "winner_id": None, "bronze": True}]
        else:
            m = side_rounds[-1][0]
            if not m:
                side_rounds[-1][0] = {"white": None, "blue": None, "winner_id": None, "bronze": True}

    def _place_in_bronze(side_rounds, player):
        if not player:
            return
        _ensure_bronze_match(side_rounds)
        m = side_rounds[-1][0]
        
        # Idempotency check
        wid = m.get("white", {}).get("id") if m.get("white") else None
        bid = m.get("blue", {}).get("id") if m.get("blue") else None
        if wid == player["id"] or bid == player["id"]:
            return

        if m.get("white") is None:
            m["white"] = player
            return
        if m.get("blue") is None:
            m["blue"] = player
            return

    def _merge_repechage_results(old_rep, new_rep):
        if not isinstance(old_rep, dict) or not isinstance(new_rep, dict):
            return
        def match_key(m):
            if not m: return None
            w = m.get("white"); b = m.get("blue")
            ids = []
            if w and w.get("id"): ids.append(w.get("id"))
            if b and b.get("id"): ids.append(b.get("id"))
            if not ids: return None
            return tuple(sorted(ids))

        wins = {}
        for side in old_rep.values():
            if not isinstance(side, dict): continue
            for round_list in side.get("rounds", []):
                for m in round_list:
                    if not m: continue
                    if m.get("winner_id") is None: continue
                    k = match_key(m)
                    if k is not None:
                        wins[k] = m.get("winner_id")

        for side in new_rep.values():
            if not isinstance(side, dict): continue
            for round_list in side.get("rounds", []):
                for m in round_list:
                    if not m: continue
                    if m.get("winner_id") is not None: continue
                    k = match_key(m)
                    if k is not None and k in wins:
                        m["winner_id"] = wins[k]

    if mode == "simple":
        final = rounds[-1][0] if rounds[-1] else None
        finalists = [final.get("white"), final.get("blue")] if final else [None, None]
        # Special case: 4 players -> bronze match between semi-final losers
        if len(rounds) == 2:
            sf_round = rounds[-2]
            l1 = _loser(sf_round[0]) if len(sf_round) > 0 else None
            l2 = _loser(sf_round[1]) if len(sf_round) > 1 else None
            bronze_match = {
                "white": l1,
                "blue": l2,
                "winner_id": None,
                "bronze": True,
            }
            draw["repechage"] = {"top": {"rounds": [[bronze_match]]}, "bottom": {"rounds": []}}
            _merge_repechage_results(prev_rep, draw["repechage"])
            return
        # For 8-player brackets use standard QF->SF structure
        if len(rounds) == 3:
            qf_round = rounds[-3]
            sf_round = rounds[-2]
            if len(qf_round) >= 4 and len(sf_round) >= 2:
                qf1_l = _loser(qf_round[0])
                qf2_l = _loser(qf_round[1])
                qf3_l = _loser(qf_round[2])
                qf4_l = _loser(qf_round[3])
                sf1_l = _loser(sf_round[0])
                sf2_l = _loser(sf_round[1])

                def _update_match_players(match, white, blue):
                    if not match: return
                    old_w = match.get("white"); old_b = match.get("blue")
                    w_ch = (old_w.get("id") if old_w else None) != (white.get("id") if white else None)
                    b_ch = (old_b.get("id") if old_b else None) != (blue.get("id") if blue else None)
                    if w_ch or b_ch:
                        match["winner_id"] = None
                    match["white"] = white
                    match["blue"] = blue

                # Reuse existing repechage if compatible (Update In Place)
                if prev_rep and \
                   prev_rep.get("top") and prev_rep.get("bottom") and \
                   len(prev_rep["top"].get("rounds",[])) >= 2 and \
                   len(prev_rep["bottom"].get("rounds",[])) >= 2:
                    
                    # Update Top
                    r0 = prev_rep["top"]["rounds"][0]
                    if r0 and r0[0]:
                        _update_match_players(r0[0], qf1_l, qf2_l)
                    _place_in_bronze(prev_rep["top"]["rounds"], sf2_l)

                    # Update Bottom
                    r0 = prev_rep["bottom"]["rounds"][0]
                    if r0 and r0[0]:
                        _update_match_players(r0[0], qf3_l, qf4_l)
                    _place_in_bronze(prev_rep["bottom"]["rounds"], sf1_l)
                    
                    draw["repechage"] = prev_rep
                    return

                # Build fresh if no compatible previous structure
                left = [_make_match(qf1_l, qf2_l, bronze=False),
                        {"white": None, "blue": None, "winner_id": None, "bronze": True}]
                right = [_make_match(qf3_l, qf4_l, bronze=False),
                         {"white": None, "blue": None, "winner_id": None, "bronze": True}]
                draw["repechage"] = {
                    "top": {"rounds": [[left[0]], [left[1]]]},
                    "bottom": {"rounds": [[right[0]], [right[1]]]},
                }
                _advance_byes_in_rounds(draw["repechage"]["top"]["rounds"], players)
                _advance_byes_in_rounds(draw["repechage"]["bottom"]["rounds"], players)
                _place_in_bronze(draw["repechage"]["top"]["rounds"], sf2_l)
                _place_in_bronze(draw["repechage"]["bottom"]["rounds"], sf1_l)
                _merge_repechage_results(prev_rep, draw["repechage"])
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
                        {"white": None, "blue": None, "winner_id": None, "bronze": True}]
                right = [_make_match(qf3_l, qf4_l, bronze=False),
                         {"white": None, "blue": None, "winner_id": None, "bronze": True}]
                draw["repechage"] = {
                    "top": {"rounds": [[left[0]], [left[1]]]},
                    "bottom": {"rounds": [[right[0]], [right[1]]]},
                }
                _advance_byes_in_rounds(draw["repechage"]["top"]["rounds"], players)
                _advance_byes_in_rounds(draw["repechage"]["bottom"]["rounds"], players)
                _place_in_bronze(draw["repechage"]["top"]["rounds"], sf2_l)
                _place_in_bronze(draw["repechage"]["bottom"]["rounds"], sf1_l)
                _merge_repechage_results(prev_rep, draw["repechage"])
                return
            draw["repechage"] = {
                "top": {"rounds": [[_make_match(None, None, bronze=True)]]},
                "bottom": {"rounds": [[_make_match(None, None, bronze=True)]]},
            }
            _merge_repechage_results(prev_rep, draw["repechage"])
            return
        sides = {}
        for idx, finalist in enumerate(finalists):
            defeated = _path_opponents(rounds, finalist["id"], include_semi=False)
            semi_loser = _semi_loser(rounds, finalist["id"])
            rep_rounds, _, _ = _generate_bracket(defeated, preserve_order=True) if defeated else ([], 0, 0)
            if not rep_rounds:
                rep_rounds = [[]]
            rep_rounds.append([{"white": None, "blue": None, "winner_id": None, "bronze": True}])
            _advance_byes_in_rounds(rep_rounds, players)
            _place_in_bronze(rep_rounds, semi_loser)
            side_key = "top" if idx == 0 else "bottom"
            sides[side_key] = {"rounds": rep_rounds}
        draw["repechage"] = sides
        _merge_repechage_results(prev_rep, draw["repechage"])
        return

    if mode == "double" and len(rounds) >= 2:
        final = rounds[-1][0] if rounds[-1] else None
        finalists = [final.get("white"), final.get("blue")] if final else [None, None]
        if not finalists[0] or not finalists[1]:
            draw["repechage"] = {
                "top": {"rounds": [[_make_match(None, None, bronze=True)]]},
                "bottom": {"rounds": [[_make_match(None, None, bronze=True)]]},
            }
            _merge_repechage_results(prev_rep, draw["repechage"])
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
            rep_rounds.append([{"white": None, "blue": None, "winner_id": None, "bronze": True}])
            _advance_byes_in_rounds(rep_rounds, players)
            _place_in_bronze(rep_rounds, bronze_opponent)
            side_key = "top" if idx == 0 else "bottom"
            sides[side_key] = {"rounds": rep_rounds}
        draw["repechage"] = sides
        _merge_repechage_results(prev_rep, draw["repechage"])
        return

    sides = {}
    for idx, finalist in enumerate(finalists):
        include_semi = (mode == "double")
        defeated = _path_opponents(rounds, finalist["id"], include_semi=include_semi)
        semi_loser = _semi_loser(rounds, finalist["id"])
        side_key = "top" if idx == 0 else "bottom"
        sides[side_key] = _build_repechage_side(defeated, semi_loser, mode)
    draw["repechage"] = sides

def generate_draw(players, repechage_mode="simple", champion_ids=None):
    pool = players[:]
    if len(pool) == 3:
        random.shuffle(pool)
        return {
            "type": "round_robin",
            "players": pool,
            "matches": _round_robin_matches(pool),
            "repechage_mode": repechage_mode,
            "num_players": len(pool),
        }
    if len(pool) == 5:
        random.shuffle(pool)
        pool_a = []
        pool_b = []
        if champion_ids:
            by_id = {p.get("id"): p for p in pool}
            champs = []
            for cid in champion_ids:
                p = by_id.get(cid)
                if p and p not in champs:
                    champs.append(p)
            for p in champs:
                if p in pool:
                    pool.remove(p)
            for i, p in enumerate(champs):
                if len(pool_a) < 2 and (i % 2 == 0 or len(pool_b) >= 3):
                    pool_a.append(p)
                elif len(pool_b) < 3:
                    pool_b.append(p)
                elif len(pool_a) < 2:
                    pool_a.append(p)
        for p in pool:
            if len(pool_a) < 2:
                pool_a.append(p)
            else:
                pool_b.append(p)
        draw = {
            "type": "pool5",
            "pools": {
                "A": {"players": pool_a, "matches": _round_robin_matches(pool_a)},
                "B": {"players": pool_b, "matches": _round_robin_matches(pool_b)},
            },
            "semis": [
                {"white": None, "blue": None, "winner_id": None},
                {"white": None, "blue": None, "winner_id": None},
            ],
            "final": {"white": None, "blue": None, "winner_id": None},
            "repechage_mode": repechage_mode,
            "num_players": len(pool),
        }
        _update_pool5(draw, pool)
        return draw
    rounds, base, n = _generate_bracket(pool, preserve_order=False, champion_ids=champion_ids)
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
    if draw.get("type") == "pool5":
        # pool5 uses advance_pool5 for match updates
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
        if first:
            rounds[round_idx+1][slot]["white"] = player
            rounds[round_idx+1][slot]["white_from"] = match_idx
        else:
            rounds[round_idx+1][slot]["blue"]  = player
            rounds[round_idx+1][slot]["blue_from"] = match_idx
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
        
        match = rounds[round_idx+1][slot]
        side = "white" if first else "blue"
        
        # If target slot is pre-filled by a placed loser (no _from), flip side
        if match.get(side) is not None and match.get(f"{side}_from") is None:
            side = "blue" if side == "white" else "white"
            
        match[side] = player
        match[f"{side}_from"] = match_idx

def advance_pool5(draw, stage, match_idx, winner_id, players):
    if draw.get("type") != "pool5":
        return
    pools = draw.get("pools", {})
    if stage == "pool_a":
        matches = pools.get("A", {}).get("matches", [])
        if 0 <= match_idx < len(matches):
            matches[match_idx]["winner_id"] = winner_id
        _update_pool5(draw, players)
        return
    if stage == "pool_b":
        matches = pools.get("B", {}).get("matches", [])
        if 0 <= match_idx < len(matches):
            matches[match_idx]["winner_id"] = winner_id
        _update_pool5(draw, players)
        return
    if stage == "semi":
        semis = draw.get("semis", [])
        if 0 <= match_idx < len(semis):
            semis[match_idx]["winner_id"] = winner_id
        _update_pool5(draw, players)
        return
    if stage == "final":
        final = draw.get("final")
        if final:
            final["winner_id"] = winner_id
        return

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
    if draw.get("type") == "pool5":
        pools = draw.get("pools", {})
        for key, stage in (("A", "pool_a"), ("B", "pool_b")):
            matches = pools.get(key, {}).get("matches", [])
            for i, m in enumerate(matches):
                p1 = m.get("p1"); p2 = m.get("p2")
                if not p1 or not p2: 
                    continue
                ids = {p1.get("id"), p2.get("id")}
                if ids == {white_id, blue_id}:
                    advance_pool5(draw, stage, i, winner_id, players)
                    return True
        for i, m in enumerate(draw.get("semis", [])):
            w = m.get("white"); b = m.get("blue")
            if not w or not b:
                continue
            ids = {w.get("id"), b.get("id")}
            if ids == {white_id, blue_id}:
                advance_pool5(draw, "semi", i, winner_id, players)
                return True
        final = draw.get("final") or {}
        w = final.get("white"); b = final.get("blue")
        if w and b:
            ids = {w.get("id"), b.get("id")}
            if ids == {white_id, blue_id}:
                advance_pool5(draw, "final", 0, winner_id, players)
                return True
        return False

    rounds = draw.get("rounds", [])
    for ri, round_list in enumerate(rounds):
        for mi, match in enumerate(round_list):
            if not match: continue
            if match.get("winner_id") is not None:
                continue
            w = match.get("white"); b = match.get("blue")
            if not w or not b: continue
            ids = {w.get("id"), b.get("id")}
            if ids == {white_id, blue_id}:
                advance_winner(draw, ri, mi, winner_id, players)
                return True
    rep = draw.get("repechage") or {}
    if isinstance(rep, dict):
        for side_key, side in rep.items():
            rounds = side.get("rounds", []) if isinstance(side, dict) else []
            for ri, round_list in enumerate(rounds):
                for mi, match in enumerate(round_list):
                    if not match: 
                        continue
                    if match.get("winner_id") is not None:
                        continue
                    w = match.get("white"); b = match.get("blue")
                    if not w or not b: 
                        continue
                    ids = {w.get("id"), b.get("id")}
                    if ids == {white_id, blue_id}:
                        advance_repechage(draw, side_key, ri, mi, winner_id, players)
                        return True
    return False
