import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta, timezone

DB_DIR = Path("data")
DB_PATH = DB_DIR / "dota2.db"
CHINA_TIMEZONE = timezone(timedelta(hours=8))


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


async def init_db():
    db = await get_db()
    await db.executescript("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;")
    await _migrate_v1(db)
    await _migrate_v2_add_quota_type(db)
    await _migrate_v3_add_smurf_tables(db)
    await db.close()


async def check_and_deduct_quota(
    openid: str, quota_type: str, limit: int = 1
) -> bool:
    """检查并扣除每日配额。返回 True 表示额度可用且已扣除。"""
    from config import settings
    if settings.dev_mode:
        return True
    today = datetime.now(CHINA_TIMEZONE).date().isoformat()
    db = await get_db()
    async with db.execute(
        "SELECT count FROM daily_quota "
        "WHERE openid = ? AND date = ? AND quota_type = ?",
        (openid, today, quota_type),
    ) as cursor:
        row = await cursor.fetchone()
    if row and row["count"] >= limit:
        await db.close()
        return False
    await db.execute(
        "INSERT INTO daily_quota (openid, date, quota_type, count) "
        "VALUES (?, ?, ?, 1) "
        "ON CONFLICT(openid, date, quota_type) DO UPDATE SET count = count + 1",
        (openid, today, quota_type),
    )
    await db.commit()
    await db.close()
    return True
