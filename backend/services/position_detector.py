"""位置判定: 英雄主位置优先，冲突时GPM仲裁"""
"""位置判定: 英雄主位置 > GPM > 辅助装备 三级仲裁"""

from services.hero_position import HERO_PRIMARY, HERO_SECONDARY
import services.hero_position as hp_module

# 归一化：HERO_PRIMARY 里有人手写了 [pos, sec1, sec2] 格式，拆成 primary + merge 到 secondary
_primary: dict[int, int] = {}
_secondary: dict[int, list[int]] = dict(HERO_SECONDARY)
for k, v in HERO_PRIMARY.items():
    if isinstance(v, list):
        _primary[k] = v[0]
        if len(v) > 1:
            existing = _secondary.get(k, [])
            for s in v[1:]:
                if s not in existing:
                    existing.append(s)
            _secondary[k] = existing
    else:
        _primary[k] = v
POSITION_NAMES = {1: "Carry", 2: "Mid", 3: "Offlane", 4: "Soft Support", 5: "Hard Support"}
POSITION_LABELS = {1: "1号位", 2: "2号位", 3: "3号位", 4: "4号位", 5: "5号位"}


def detect_positions(players: list[dict]) -> list[dict]:
    """为每个玩家分配 1-5 号位"""
    radiant = [p for p in players if p.get("isRadiant")]
    dire = [p for p in players if not p.get("isRadiant")]

    for team in [radiant, dire]:
        _assign_team(team)

    return players


def _assign_team(team: list[dict]):
    """为一个阵营的5个玩家分配位置"""
    # 初始：每人取英雄主位置
    for p in team:
        p["_pos"] = _primary.get(p.get("hero_id", 0))
        p["_done"] = False

    # 第一轮：无冲突直接分配
    for p in team:
        pos = p["_pos"]
        if pos is not None:
            others = [o for o in team if o is not p and o.get("_pos") == pos]
            if not others:
                p["position"] = pos
                p["_done"] = True

    # 第二轮：冲突解决——同位置多人，GPM高者保留
    claimed = {p["_pos"] for p in team if p["_pos"] is not None}
    for pos in claimed:
        fighters = [p for p in team if p["_pos"] == pos and not p["_done"]]
        if len(fighters) >= 2:
            # 核心位（1-3）：GPM高者保留；辅助位（4-5）：辅助得分高者保留
            if pos <= 3:
                fighters.sort(key=lambda x: (x.get("gold_per_min", 0), -_support_score(x)), reverse=True)
            else:
                fighters.sort(key=lambda x: _support_score(x), reverse=True)
            winner = fighters[0]
            winner["position"] = pos
            winner["_done"] = True
            for f in fighters[1:]:
                f["_pos"] = None

    # 第三轮：未分配者→次要位置→剩余空位按GPM填
    undone = [p for p in team if not p["_done"]]
    taken = {p["position"] for p in team if p.get("_done")}
    free = sorted(set(range(1, 6)) - taken)

    # GPM排序（只用于未分配玩家）
    undone.sort(key=lambda x: x.get("gold_per_min", 0), reverse=True)

    for p in undone:
        secondary = _secondary.get(p.get("hero_id", 0), [])
        assigned = False
        for s in secondary:
            if s in free:
                p["position"] = s
                free.remove(s)
                assigned = True
                break
        if not assigned and free:
            # GPM高的拿高优先级空位
            p["position"] = free.pop(0)
            assigned = True
        if not assigned:
            p["position"] = 99

    # 清理
    for p in team:
        pos = p.get("position", 99)
        p["position_name"] = POSITION_NAMES.get(pos, "Unknown")
        p["position_label"] = POSITION_LABELS.get(pos, "未知")
        p.pop("_pos", None)
        p.pop("_done", None)
SUPPORT_ITEMS = {
    "glimmer_cape", "force_staff", "mekansm", "guardian_greaves",
    "solar_crest", "lotus_orb", "pipe", "crimson_guard",
    "holy_locket", "spirit_vessel", "arcane_boots", "aether_lens",
    "urn_of_shadows", "medallion_of_courage", "buckler", "headdress",
    "ring_of_basilius", "vladsmir", "drum_of_endurance", "boots_of_bearing",
    "ward_observer", "ward_sentry",
}


def _support_score(p: dict) -> int:
    """评估玩家辅助倾向得分：0=纯核心, 10=纯辅助"""
    score = 0
    # 辅助装 + 眼
    purchase_log = p.get("purchase_log") or []
    bought_support = 0
    bought_wards = 0
    for entry in purchase_log:
        key = entry.get("key") if isinstance(entry, dict) else (entry[1] if isinstance(entry, (list, tuple)) and len(entry) > 1 else None)
        if not key:
            continue
        if key in SUPPORT_ITEMS:
            bought_support += 1
        if key in ("ward_observer", "ward_sentry"):
            bought_wards += 1
    # 眼: 买了3组以上→高分
    if bought_wards >= 6: score += 3
    elif bought_wards >= 4: score += 2
    elif bought_wards >= 2: score += 1
    if bought_support >= 3: score += 4
    elif bought_support >= 2: score += 3
    elif bought_support >= 1: score += 1
    # GPM
    gpm = p.get("gold_per_min", 0)
    if gpm < 350: score += 2
    elif gpm < 450: score += 1
    return score
