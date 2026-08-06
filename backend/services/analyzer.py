"""AI 分析引擎 — 通过 openai/anthropic SDK 调用多模型，生成赛后复盘"""
import json
from config import settings
from services.position_detector import detect_positions
from services.opendota import get_heroes
from services.hero_cn import cn_name


# ---- 分段基准表 (用于给 AI 提供参考系) ----
SKILL_BENCHMARKS = {
    "normal": {
        "label": "Normal (约2000 MMR以下)",
        "carry_gpm": 430, "carry_lh_per_min": 5.0,
        "mid_gpm": 420, "mid_kda_min": 2.0,
        "offlane_gpm": 380,
        "support_obs": 8, "support_sen": 4,
    },
    "high": {
        "label": "High (约2000-3700 MMR)",
        "carry_gpm": 500, "carry_lh_per_min": 6.0,
        "mid_gpm": 480, "mid_kda_min": 2.5,
        "offlane_gpm": 420,
        "support_obs": 12, "support_sen": 6,
    },
    "very_high": {
        "label": "Very High (约3700+ MMR)",
        "carry_gpm": 580, "carry_lh_per_min": 7.0,
        "mid_gpm": 550, "mid_kda_min": 3.0,
        "offlane_gpm": 480,
        "support_obs": 16, "support_sen": 8,
    },
}

SYSTEM_PROMPT = """你是一个 Dota 2 赛后分析师，风格毒舌又客观，幽默但不刻薄。
你的任务是根据提供的比赛数据，生成一场赛后复盘分析。

输出格式：纯 JSON，不要包含 markdown 代码块标记。结构如下：

{
  "mvp": {
    "player_name": "选手名（必须与上面选手数据中的名字完全一致）",
    "hero_name": "英雄中文名",
    "reason": "为什么他是MVP（2-3句话，用比赛中的具体表现说明，不要套话）"
  },
  "scapegoat": {
    "player_name": "选手名（必须与上面选手数据中的名字完全一致）",
    "hero_name": "英雄中文名",
    "reason": "为什么他是本场背锅侠（2-3句话，指出关键失误，语气可以戏谑但不能人身攻击）"
  },
  "position_evals": [
    {
      "player_name": "选手名（必须与上面选手数据中的名字完全一致）",
      "position": 1,
      "is_qualified": true/false,
      "score": 0-100,
      "summary": "一句总评",
      "highlights": ["亮点1", "亮点2"],
      "improvements": ["改进建议1", "改进建议2", "改进建议3"]
    }
  ],
  "timeline": [
    {
      "time": 秒数,
      "event_type": "kill/tower/roshan/item/aegis",
      "description": "事件描述",
      "importance": "low/medium/high/critical"
    }
  ],
  "game_summary": "整场比赛的一句话总结（幽默风格）"
}

评分原则：
- 每个选手都要给出一条位置评估，共10条
- MVP和背锅侠必须提供 hero_name（英雄中文名），方便后续匹配
- MVP是全场贡献最大的人，不一定是数据最华丽的，但一定是最关键的
- 背锅侠是全场失误最致命的人，用数据和具体事件支撑
- 位置评估要基于该分段基准和该位置职责来判断
- 改进建议要具体可操作，不要说"多打钱""少送"这种废话
- 高分段的评判标准应该更严苛"""
def get_api_config(provider: str) -> tuple[str, str, str]:
    """返回 (api_key, api_base, default_model)"""
    configs = {
        "openai": (settings.openai_api_key, "https://api.openai.com/v1", "gpt-4o"),
        "deepseek": (settings.deepseek_api_key, "https://api.deepseek.com/v1", "deepseek-chat"),
        "claude": (settings.anthropic_api_key, "", "claude-sonnet-4-20250514"),
    }
    if provider not in configs:
        provider = settings.default_ai_provider
    return configs[provider]


def build_match_context(match_data: dict, heroes: dict[int, dict]) -> str:
    """把比赛原始数据构建成 AI 可理解的文本上下文"""
    players = detect_positions(match_data.get("players", []))
    overview = match_data
    duration_min = overview.get("duration", 0) // 60
    skill_level = _skill_str(overview)
    benchmark = _get_benchmark(overview)

    lines = []
    lines.append(f"## 比赛概览")
    lines.append(f"- 比赛ID: {overview.get('match_id')}")
    lines.append(f"- 时长: {duration_min}分钟")
    lines.append(f"- 分段: {skill_level}")
    lines.append(f"- 天辉: {overview.get('radiant_score', '?')} | 夜魇: {overview.get('dire_score', '?')}")
    lines.append(f"- 天辉胜利: {'是' if overview.get('radiant_win') else '否'}")

    lines.append(f"\n## 分段基准参考 (你评估时的参照系)")
    lines.append(f"- Carry GPM基准: {benchmark['carry_gpm']} | 正补/分: {benchmark['carry_lh_per_min']}")
    lines.append(f"- Mid GPM基准: {benchmark['mid_gpm']}")
    lines.append(f"- Offlane GPM基准: {benchmark['offlane_gpm']}")
    lines.append(f"- 辅助插眼基准: {benchmark['support_obs']}个假眼 | {benchmark['support_sen']}个真眼")

    lines.append(f"\n## 选手数据 (已按位置排序)")
    for p in sorted(players, key=lambda x: x.get("position", 99)):
        pos = p.get("position_label", "未知")
        hero = heroes.get(p.get("hero_id"), {})
        hero_name = cn_name(hero.get("localized_name", "")) or f"Hero_{p.get('hero_id')}"
        kda = f"{p.get('kills',0)}/{p.get('deaths',0)}/{p.get('assists',0)}"
        gpm = p.get("gold_per_min", 0)
        xpm = p.get("xp_per_min", 0)
        lh = p.get("last_hits", 0)
        dn = p.get("denies", 0)
        hd = p.get("hero_damage", 0)
        td = p.get("tower_damage", 0)
        hh = p.get("hero_healing", 0)
        nw = p.get("net_worth", 0)
        is_win = p.get("isRadiant") == overview.get("radiant_win")

        lines.append(f"\n### {pos} - {hero_name} (选手: {p.get('personaname', p.get('account_id', 'Unknown'))})")
        lines.append(f"  KDA: {kda} | GPM: {gpm} | XPM: {xpm} | 经济: {nw}")
        lines.append(f"  正补: {lh} | 反补: {dn} | 英雄伤害: {hd} | 塔伤害: {td} | 治疗: {hh}")
        lines.append(f"  阵营: {'胜' if is_win else '负'}")

        # 出装时间线
        purchase_log = p.get("purchase_log", [])
        if purchase_log:
            key_items = ["blink", "black_king_bar", "battle_fury", "radiance",
                         "aghanims_scepter", "refresher", "divine_rapier",
                         "glimmer_cape", "force_staff", "mekansm", "pipe",
                         "crimson_guard", "guardian_greaves", "lotus_orb", "solar_crest"]
            items_bought = []
            for entry in purchase_log:
                if entry.get("key") in key_items:
                    time_min = entry.get("time", 0) // 60
                    item_key = entry.get("key", "").replace("_", " ")
                    items_bought.append(f"{item_key}@{time_min}分钟")
            if items_bought:
                lines.append(f"  关键装备: {', '.join(items_bought[:8])}")

    return "\n".join(lines)


def _skill_str(data: dict) -> str:
    skill = data.get("skill")
    avg_mmr = data.get("avg_mmr")
    lobby_type = data.get("lobby_type", 0)
    labels = {1: "Normal", 2: "High", 3: "Very High"}
    if skill and skill in labels:
        label = labels[skill]
        mmr_str = f" (avg {avg_mmr})" if avg_mmr else ""
        return f"{label}{mmr_str}"
    elif lobby_type == 7:
        return "天梯" if not avg_mmr else f"天梯 avg {avg_mmr}"
    else:
        return "普通匹配"


def _get_benchmark(data: dict) -> dict:
    skill = data.get("skill")
    labels = {1: "normal", 2: "high", 3: "very_high"}
    key = labels.get(skill, "high")
    return SKILL_BENCHMARKS.get(key, SKILL_BENCHMARKS["high"])


async def analyze_match(match_data: dict, provider: str = "deepseek", model: str | None = None) -> dict:
    """核心分析函数: 用 AI 分析比赛"""
    api_key, api_base, default_model = get_api_config(provider)
    if model is None:
        model = default_model

    heroes = await get_heroes()
    context = build_match_context(match_data, heroes)

    user_prompt = f"请分析以下 Dota 2 比赛:\n\n{context}"

    if provider == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        if model is None:
            model = "claude-sonnet-4-20250514"
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0.8,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = message.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=api_base)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=8192,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError(f"AI 返回空内容。model={model}, finish_reason={response.choices[0].finish_reason}")

    # 清理可能的 markdown 代码块包裹
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        ai_result = json.loads(content)
    except json.JSONDecodeError:
        # 尝试提取 JSON 块
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            ai_result = json.loads(match.group())
        else:
            raise ValueError(f"AI 返回格式无法解析: {content[:500]}")

    # 组装最终结果
    players = match_data.get("players", [])
    players = detect_positions(players)
    overview = match_data

    player_cards = _build_player_cards(players, heroes, overview)
    radiant_players = [c for c in player_cards if c["is_radiant"]]
    dire_players = [c for c in player_cards if not c["is_radiant"]]

    def _find_card(name: str, ai_entry: dict, exclude: set = None) -> dict:
        """按玩家名匹配 player_card，支持模糊匹配，exclude 用于排除已选中的卡"""
        exclude = exclude or set()
        name = (name or "").strip()
        ai_hero = (ai_entry.get("hero_name", "") or "").strip()

        def _match(c):
            cn = c["player_name"].strip()
            # 优先 hero_name 精确匹配
            if ai_hero and c["hero_name"] == ai_hero:
                return True
            # 其次 player_name 模糊匹配
            if name:
                nl = name.lower()
                cl = cn.lower()
                if cn == name or cl == nl or name in cn or cn in name:
                    return True
            return False

        candidates = [c for c in player_cards if c["player_name"] not in exclude and _match(c)]
        if candidates:
            return candidates[0]
        # 放宽：只用 hero_name 匹配
        if ai_hero:
            for c in player_cards:
                if c["player_name"] not in exclude and c["hero_name"] == ai_hero:
                    return c
        # 最终兜底：返回第一个未被排除的卡
        for c in player_cards:
            if c["player_name"] not in exclude:
                return c
        return player_cards[0]

    mvp_card = _find_card(ai_result["mvp"].get("player_name", ""), ai_result["mvp"])
    sg_card = _find_card(ai_result["scapegoat"].get("player_name", ""), ai_result["scapegoat"], {mvp_card["player_name"]})

    # u6821u9a8c1uff1aMVP u548cu80ccu9505u4fa0u4e0du80fdu662fu540cu4e00u4e2au4eba
    if mvp_card["player_name"] == sg_card["player_name"]:
        _sg_name = ai_result["scapegoat"].get("player_name", "").strip()
        _sg_hero = ai_result["scapegoat"].get("hero_name", "").strip()
        for c in player_cards:
            if c["player_name"] != mvp_card["player_name"]:
                if (_sg_hero and c["hero_name"] == _sg_hero) or (_sg_name and _sg_name.lower() in c["player_name"].lower()):
                    sg_card = c
                    break
        else:
            _losers = [c for c in player_cards if not c["is_winner"] and c["player_name"] != mvp_card["player_name"]]
            if _losers:
                _losers.sort(key=lambda x: float(x["kda"].split("/")[0]) / max(1, float(x["kda"].split("/")[1])))
                sg_card = _losers[0]

    # u6821u9a8c2uff1au65f6u95f4u7ebfu65f6u95f4u4e0du80fdu8d85u8fc7u6bd4u8d5bu65f6u957f
    _max_time = overview.get("duration", 0)
    for ev in ai_result.get("timeline", []):
        if ev.get("time", 0) > _max_time:
            ev["time"] = _max_time - 10
    ai_result["timeline"] = [ev for ev in ai_result.get("timeline", []) if ev.get("time", 0) >= 0]

def _apply_card_match(pe: dict, c: dict):
    """将 player_card 的信息同步到 position_eval 条目中"""
    pe["position"] = c["position"]
    pe["player_name"] = c["player_name"]
    pe["hero_name"] = c["hero_name"]
    pe["is_radiant"] = c["is_radiant"]
    pe["is_qualified"] = pe.get("is_qualified", True)
    pe["score"] = max(0, min(100, pe.get("score", 50)))



    # 校正 AI 返回的 position_evals：用探测器分配的 correct position 覆盖，确保每队1-5号位唯一
    _corrected_evals = []
    _matched_cards = set()  # 追踪已匹配的 player_card 索引，防止重复匹配
    for pe in ai_result.get("position_evals", []):
        _pe_name = (pe.get("player_name", "") or "").strip()
        _pe_hero = (pe.get("hero_name", "") or "").strip()
        matched = False
        # 第一轮：player_name 精确匹配未使用的 card
        for i, c in enumerate(player_cards):
            if i in _matched_cards:
                continue
            if _pe_name and (c["player_name"].strip() == _pe_name or c["player_name"].strip().lower() == _pe_name.lower() or _pe_name in c["player_name"] or c["player_name"] in _pe_name):
                _apply_card_match(pe, c)
                _corrected_evals.append(pe)
                _matched_cards.add(i)
                matched = True
                break
        # 第二轮：hero_name 匹配未使用的 card
        if not matched and _pe_hero:
            for i, c in enumerate(player_cards):
                if i in _matched_cards:
                    continue
                if c["hero_name"] == _pe_hero or _pe_hero in c["hero_name"] or c["hero_name"] in _pe_hero:
                    _apply_card_match(pe, c)
                    _corrected_evals.append(pe)
                    _matched_cards.add(i)
                    matched = True
                    break
        # 无法匹配的 eval 也保留，但标记为未知阵营（兜底）
        if not matched:
            pe["is_radiant"] = False
            pe["is_qualified"] = pe.get("is_qualified", True)
            pe["score"] = max(0, min(100, pe.get("score", 50)))
            _corrected_evals.append(pe)
    ai_result["position_evals"] = _corrected_evals
    return {
        "mvp": {**mvp_card, "reason": ai_result["mvp"]["reason"]},
        "scapegoat": {**sg_card, "reason": ai_result["scapegoat"]["reason"]},
        "position_evals": ai_result["position_evals"],
        "timeline": ai_result["timeline"],
        "player_cards": player_cards,
        "radiant_players": radiant_players,
        "dire_players": dire_players,
        "game_summary": ai_result.get("game_summary", ""),
        "radiant_win": overview.get("radiant_win", False),
        "duration": overview.get("duration", 0),
        "skill_level": _skill_str(overview),
        "avg_mmr": overview.get("avg_mmr"),
    }


def _build_player_cards(players: list[dict], heroes: dict[int, dict], overview: dict) -> list[dict]:
    """构建玩家数据卡片"""
    cards = []
    radiant_win = overview.get("radiant_win", False)
    for p in sorted(players, key=lambda x: x.get("position", 99)):
        hero = heroes.get(p.get("hero_id"), {})
        en_name = hero.get("localized_name", "")
        is_radiant = p.get("isRadiant", False)
        cards.append({
            "player_name": p.get("personaname", str(p.get("account_id", "Unknown"))),
            "hero_name": cn_name(en_name) or f"Hero_{p.get('hero_id')}",
            "hero_icon": f"/hero-img/{hero.get('name', 'unknown').replace('npc_dota_hero_', '')}.png",
            "position": p.get("position", 0),
            "is_radiant": is_radiant,
            "kda": f"{p.get('kills',0)}/{p.get('deaths',0)}/{p.get('assists',0)}",
            "gpm": p.get("gold_per_min", 0),
            "xpm": p.get("xp_per_min", 0),
            "net_worth": p.get("net_worth", 0),
            "last_hits": p.get("last_hits", 0),
            "hero_damage": p.get("hero_damage", 0),
            "tower_damage": p.get("tower_damage", 0),
            "obs_placed": p.get("obs_placed", 0),
            "sen_placed": p.get("sen_placed", 0),
            "is_winner": p.get("isRadiant") == radiant_win,
        })
    return cards
