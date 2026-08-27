import json
import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

DB_DIR = Path("data")
DB_PATH = DB_DIR / "dota2.db"
CHINA_TIMEZONE = timezone(timedelta(hours=8))
DAILY_QUOTA_LIMIT = 3
QUOTA_TYPE_ANALYSIS = "analysis"


async def get_db() -> aiosqlite.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


async def _migrate_v1(db: aiosqlite.Connection):
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS match_analyses (
            id TEXT PRIMARY KEY,
            match_id INTEGER NOT NULL,
            share_id TEXT UNIQUE NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            raw_data TEXT NOT NULL,
            analysis_result TEXT NOT NULL,
            player_names TEXT NOT NULL,
            hero_names TEXT NOT NULL,
            skill_level TEXT,
            avg_mmr INTEGER,
            radiant_win BOOLEAN,
            duration INTEGER,
            openid TEXT DEFAULT "",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_match_id ON match_analyses(match_id);
        CREATE INDEX IF NOT EXISTS idx_share_id ON match_analyses(share_id);
    """)
    await db.commit()


async def _migrate_v2_add_quota_type(db: aiosqlite.Connection):
    """v2: daily_quota 从单一 count 迁移到 quota_type 方案"""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_quota'"
    )
    old_table = await cursor.fetchone()
    if not old_table:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS daily_quota (
                openid TEXT NOT NULL,
                date TEXT NOT NULL,
                quota_type TEXT NOT NULL DEFAULT 'analysis',
                count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (openid, date, quota_type)
            );
        """)
        await db.commit()
        return
    try:
        await db.execute("SELECT quota_type FROM daily_quota LIMIT 0")
    except Exception:
        await db.executescript("""
            CREATE TABLE daily_quota_v2 (
                openid TEXT NOT NULL,
                date TEXT NOT NULL,
                quota_type TEXT NOT NULL DEFAULT 'analysis',
                count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (openid, date, quota_type)
            );
            INSERT OR IGNORE INTO daily_quota_v2
                (openid, date, quota_type, count, created_at)
            SELECT openid, date, 'analysis', count, created_at
            FROM daily_quota;
            DROP TABLE daily_quota;
            ALTER TABLE daily_quota_v2 RENAME TO daily_quota;
        """)
    await db.commit()


async def _migrate_v3_add_smurf_tables(db: aiosqlite.Connection):
    """v3: 小号检测缓存表"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS player_profile_cache (
            account_id INTEGER PRIMARY KEY,
            data TEXT NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS player_match_cache (
            match_id INTEGER PRIMARY KEY,
            account_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pmc_account
            ON player_match_cache(account_id);
        CREATE TABLE IF NOT EXISTS benchmark_cache (
            hero_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (hero_id)
        );
        CREATE TABLE IF NOT EXISTS smurf_check_cache (
            account_id INTEGER PRIMARY KEY,
            last_match_count INTEGER NOT NULL DEFAULT 0,
            result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.commit()


async def _migrate_v4_add_match_analysis_cache(db: aiosqlite.Connection):
    """v4: 比赛分析增加一份按 match_id 唯一共享的权威缓存表"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS match_analysis_cache (
            match_id INTEGER PRIMARY KEY,
            share_id TEXT UNIQUE NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            raw_data TEXT NOT NULL,
            analysis_result TEXT NOT NULL,
            player_names TEXT NOT NULL,
            hero_names TEXT NOT NULL,
            skill_level TEXT,
            avg_mmr INTEGER,
            radiant_win BOOLEAN,
            duration INTEGER,
            openid TEXT DEFAULT "",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.commit()


async def _migrate_v5_add_users_table(db: aiosqlite.Connection):
    """v5: 用户表 — 微信身份与 Steam 账号绑定 + Dota 档案缓存"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            openid TEXT PRIMARY KEY,
            steam_id64 TEXT NOT NULL UNIQUE,
            account_id INTEGER NOT NULL,
            steam_name TEXT,
            avatar TEXT,
            profile_url TEXT,
            rank_tier INTEGER,
            rank_name TEXT,
            mmr_estimate INTEGER,
            win_rate REAL,
            total_games INTEGER,
            main_position INTEGER,
            main_position_label TEXT,
            refreshed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_users_account ON users(account_id);
    """)
    await db.commit()


async def _migrate_v6_add_challenge_tables(db: aiosqlite.Connection):
    """v6: 约战 — 活动表 + 参与者表（报名时快照资料，解绑也不丢展示）"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS challenges (
            id TEXT PRIMARY KEY,
            creator_openid TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            activity_time TEXT NOT NULL,
            mmr_min INTEGER,
            mmr_max INTEGER,
            max_players INTEGER NOT NULL DEFAULT 10,
            mode TEXT NOT NULL DEFAULT 'free',
            team_a_name TEXT DEFAULT '天辉',
            team_b_name TEXT DEFAULT '夜魇',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_challenges_status
            ON challenges(status, activity_time);
        CREATE TABLE IF NOT EXISTS challenge_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT NOT NULL,
            openid TEXT NOT NULL,
            team INTEGER NOT NULL DEFAULT -1,
            steam_name TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            rank_name TEXT,
            mmr INTEGER,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (challenge_id, openid)
        );
        CREATE INDEX IF NOT EXISTS idx_cp_challenge
            ON challenge_participants(challenge_id);
        CREATE INDEX IF NOT EXISTS idx_cp_openid
            ON challenge_participants(openid);
    """)
    await db.commit()


async def _migrate_v7_rank_tier_gates(db: aiosqlite.Connection):
    """v7: 约战门槛从 MMR 改为段位 (rank_tier)。保留旧 mmr_min/mmr_max 列不删，新代码只用 rank_tier_*。"""
    async with db.execute("PRAGMA table_info(challenges)") as cursor:
        rows = await cursor.fetchall()
    cols = {r[1] for r in rows}
    if "rank_tier_min" not in cols:
        await db.execute("ALTER TABLE challenges ADD COLUMN rank_tier_min INTEGER")
    if "rank_tier_max" not in cols:
        await db.execute("ALTER TABLE challenges ADD COLUMN rank_tier_max INTEGER")

    async with db.execute("PRAGMA table_info(challenge_participants)") as cursor:
        rows = await cursor.fetchall()
    pcols = {r[1] for r in rows}
    if "rank_tier" not in pcols:
        await db.execute("ALTER TABLE challenge_participants ADD COLUMN rank_tier INTEGER")
    await db.commit()


async def _migrate_v8_challenge_matches(db: aiosqlite.Connection):
    """v8: 约战挂比赛 — 发起人录入比赛ID，按 account_id 自动归属到参与者。"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS challenge_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT NOT NULL,
            match_id INTEGER NOT NULL,
            submitted_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (challenge_id, match_id)
        );
        CREATE INDEX IF NOT EXISTS idx_cm_challenge
            ON challenge_matches(challenge_id);
    """)
    await db.commit()


async def _migrate_v9_challenge_match_players(db: aiosqlite.Connection):
    """v9: 持久化每场比赛 10 个 player 的归属 + 雷达数据，避免重复调 OpenDota。

    录入时一次性写入；GET /matches 走 redis 缓存 + 本表兜底。
    主页胜率也从本表 SUM(is_winner) 统计。
    """
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS challenge_match_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT NOT NULL,
            match_id INTEGER NOT NULL,
            openid TEXT,
            account_id INTEGER,
            player_name TEXT DEFAULT '',
            is_radiant INTEGER NOT NULL DEFAULT 0,
            is_winner INTEGER NOT NULL DEFAULT 0,
            hero_id INTEGER,
            hero_name TEXT,
            hero_icon TEXT,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            gpm INTEGER DEFAULT 0,
            xpm INTEGER DEFAULT 0,
            hero_damage INTEGER DEFAULT 0,
            tower_damage INTEGER DEFAULT 0,
            healing INTEGER DEFAULT 0,
            last_hits INTEGER DEFAULT 0,
            denies INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            radar_kda REAL,
            radar_eco REAL,
            radar_exp REAL,
            radar_dmg REAL,
            radar_push REAL,
            radar_sustain REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_cmp_openid
            ON challenge_match_players(openid);
        CREATE INDEX IF NOT EXISTS idx_cmp_challenge
            ON challenge_match_players(challenge_id);
        CREATE INDEX IF NOT EXISTS idx_cmp_match
            ON challenge_match_players(match_id);
    """)
    await db.commit()


async def _migrate_v10_challenge_match_meta(db: aiosqlite.Connection):
    """v10: challenge_matches 补比赛级字段 duration/score/avg_mmr，DB 兜底读时不丢信息。"""
    async with db.execute("PRAGMA table_info(challenge_matches)") as cursor:
        rows = await cursor.fetchall()
    cols = {r[1] for r in rows}
    for col, decl in [
        ("duration", "INTEGER DEFAULT 0"),
        ("radiant_score", "INTEGER DEFAULT 0"),
        ("dire_score", "INTEGER DEFAULT 0"),
        ("avg_mmr", "INTEGER"),
    ]:
        if col not in cols:
            await db.execute(f"ALTER TABLE challenge_matches ADD COLUMN {col} {decl}")
    await db.commit()


async def _migrate_v11_user_rank_history(db: aiosqlite.Connection):
    """v11: user_rank_history 记录用户段位变化, 用于历史段位梯状图。

    OpenDota 公开 API 不暴露历史段位(rank_tier_history 私有), 只能自己跟踪。
    每次绑定/刷新档案时插入一条记录, 按年聚合后画梯状图。
    同时回填一次: 把 users 表现有 rank_tier 作为初始记录。
    """
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS user_rank_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid TEXT NOT NULL,
            account_id INTEGER NOT NULL,
            rank_tier INTEGER,
            rank_name TEXT,
            recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_urh_openid ON user_rank_history(openid);
        CREATE INDEX IF NOT EXISTS idx_urh_account ON user_rank_history(account_id);
        CREATE INDEX IF NOT EXISTS idx_urh_recorded ON user_rank_history(recorded_at);
    """)
    # 一次性回填: 从 users 表把当前 rank_tier 作为最早记录 (使用 refreshed_at 时间戳)
    await db.execute(
        """INSERT INTO user_rank_history (openid, account_id, rank_tier, rank_name, recorded_at)
           SELECT openid, account_id, rank_tier, rank_name,
                  COALESCE(refreshed_at, CURRENT_TIMESTAMP)
           FROM users
           WHERE rank_tier IS NOT NULL
             AND openid NOT IN (SELECT DISTINCT openid FROM user_rank_history)"""
    )
    await db.commit()


async def init_db():
    db = await get_db()
    await db.executescript("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;")
    await _migrate_v1(db)
    await _migrate_v2_add_quota_type(db)
    await _migrate_v3_add_smurf_tables(db)
    await _migrate_v4_add_match_analysis_cache(db)
    await _migrate_v5_add_users_table(db)
    await _migrate_v6_add_challenge_tables(db)
    await _migrate_v7_rank_tier_gates(db)
    await _migrate_v8_challenge_matches(db)
    await _migrate_v9_challenge_match_players(db)
    await _migrate_v10_challenge_match_meta(db)
    await _migrate_v11_user_rank_history(db)
    await db.close()


async def check_and_deduct_quota(
    openid: str,
    quota_type: str = QUOTA_TYPE_ANALYSIS,
    limit: int = DAILY_QUOTA_LIMIT,
) -> bool:
    """检查并扣除每日配额。返回 True 表示额度可用且已扣除。"""
    from config import settings
    if settings.dev_mode:
        return True
    today = datetime.now(CHINA_TIMEZONE).date().isoformat()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT COALESCE(SUM(count), 0) AS used FROM daily_quota "
            "WHERE openid = ? AND date = ?",
            (openid, today),
        ) as cursor:
            row = await cursor.fetchone()
        used = row["used"] if row else 0
        if used >= limit:
            return False
        await db.execute(
            "INSERT INTO daily_quota (openid, date, quota_type, count) "
            "VALUES (?, ?, ?, 1) "
            "ON CONFLICT(openid, date, quota_type) DO UPDATE SET count = count + 1",
            (openid, today, quota_type),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def get_quota_usage(openid: str, quota_type: str = None) -> int:
    """返回今天已经使用的额度。"""
    from config import settings
    if settings.dev_mode:
        return 0
    today = datetime.now(CHINA_TIMEZONE).date().isoformat()
    db = await get_db()
    try:
        async with db.execute(
            "SELECT COALESCE(SUM(count), 0) AS used FROM daily_quota "
            "WHERE openid = ? AND date = ?",
            (openid, today),
        ) as cursor:
            row = await cursor.fetchone()
        return row["used"] if row else 0
    finally:
        await db.close()


async def get_cached_analysis_by_match(match_id: int) -> Optional[dict]:
    """按比赛 ID 读取共享缓存。

    新数据优先从 match_analysis_cache 读取；旧版本已经写进
    match_analyses 的记录会在第一次命中时回填到新表。
    """
    db = await get_db()
    try:
        async with db.execute(
            """SELECT analysis_result, share_id, provider, model
               FROM match_analysis_cache
               WHERE match_id = ?""",
            (match_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            result = json.loads(row["analysis_result"])
            if not result.get("share_id"):
                result["share_id"] = row["share_id"]
            if not result.get("provider"):
                result["provider"] = row["provider"]
            if not result.get("model"):
                result["model"] = row["model"]
            return result

        async with db.execute(
            """SELECT analysis_result, share_id, provider, model,
                      raw_data, player_names, hero_names, skill_level,
                      avg_mmr, radiant_win, duration, openid
               FROM match_analyses
               WHERE match_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (match_id,),
        ) as cursor:
            legacy = await cursor.fetchone()
        if not legacy:
            return None

        result = json.loads(legacy["analysis_result"])
        result["share_id"] = legacy["share_id"]
        if not result.get("provider"):
            result["provider"] = legacy["provider"]
        if not result.get("model"):
            result["model"] = legacy["model"]

        await db.execute(
            """INSERT OR IGNORE INTO match_analysis_cache
               (match_id, share_id, provider, model, raw_data,
                analysis_result, player_names, hero_names, skill_level,
                avg_mmr, radiant_win, duration, openid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                match_id,
                legacy["share_id"],
                legacy["provider"],
                legacy["model"],
                legacy["raw_data"],
                json.dumps(result, ensure_ascii=False),
                legacy["player_names"],
                legacy["hero_names"],
                legacy["skill_level"],
                legacy["avg_mmr"],
                legacy["radiant_win"],
                legacy["duration"],
                legacy["openid"],
            ),
        )
        await db.commit()
        return result
    finally:
        await db.close()


async def save_match_analysis_cache(
    db: aiosqlite.Connection,
    *,
    match_id: int,
    share_id: str,
    provider: str,
    model: str,
    raw_data: str,
    analysis_result: str,
    player_names: str,
    hero_names: str,
    skill_level: str,
    avg_mmr: Optional[int],
    radiant_win: bool,
    duration: int,
    openid: str,
) -> None:
    """写入一场比赛唯一的共享分析缓存，重复写入不会覆盖已有结果。"""
    await db.execute(
        """INSERT INTO match_analysis_cache
           (match_id, share_id, provider, model, raw_data,
            analysis_result, player_names, hero_names, skill_level,
            avg_mmr, radiant_win, duration, openid, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(match_id) DO NOTHING""",
        (
            match_id,
            share_id,
            provider,
            model,
            raw_data,
            analysis_result,
            player_names,
            hero_names,
            skill_level,
            avg_mmr,
            radiant_win,
            duration,
            openid,
        ),
    )
