from pydantic import BaseModel
from typing import Optional


# ---- 请求 ----
class AnalyzeRequest(BaseModel):
    match_id: int
    provider: Optional[str] = None
    model: Optional[str] = None
    openid: Optional[str] = None


class PlayerSearchRequest(BaseModel):
    player_id: int
    limit: int = 20


# ---- AI 分析后的结构化输出 ----
class PositionEval(BaseModel):
    position: int
    position_name: str
    is_radiant: bool
    player_name: str
    hero_name: str
    is_qualified: bool
    score: int  # 0-100
    summary: str
    highlights: list[str]
    improvements: list[str]


class PlayerCard(BaseModel):
    player_name: str
    hero_name: str
    hero_icon: str
    position: int
    kda: str
    gpm: int
    xpm: int
    net_worth: int
    last_hits: int
    hero_damage: int
    tower_damage: int
    obs_placed: int
    sen_placed: int
    is_winner: bool
    account_id: int


class TimelineEvent(BaseModel):
    time: int  # seconds
    event_type: str  # kill, tower, roshan, item, aegis
    description: str
    importance: str  # low, medium, high, critical


class AnalysisResult(BaseModel):
    share_id: str
    match_id: int
    provider: str
    model: str
    radar_title: str
    mvp: PlayerCard
    mvp_reason: str
    scapegoat: PlayerCard
    scapegoat_reason: str
    position_evals: list[PositionEval]
    timeline: list[TimelineEvent]
    player_cards: list[PlayerCard]
    team_comparison: dict
    skill_level: str
    avg_mmr: Optional[int]
    radiant_win: bool
    duration: int


class MatchListItem(BaseModel):
    match_id: int
    hero_name: str
    hero_icon: str
    kills: int
    deaths: int
    assists: int
    is_win: bool
    duration: int
    start_time: int
    skill: Optional[str]


class PlayerMatchesResponse(BaseModel):
    player_name: str
    matches: list[MatchListItem]


class ShareResponse(BaseModel):
    share_id: str
    share_url: str
