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


async def init_db():
    db = await get_db()
    await db.executescript("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;")
    await _migrate_v1(db)
    await _migrate_v2_add_quota_type(db)
    await _migrate_v3_add_smurf_tables(db)
    await _migrate_v4_add_match_analysis_cache(db)
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
