import aiosqlite
from pathlib import Path

DB_DIR = Path("data")
DB_PATH = DB_DIR / "dota2.db"


async def get_db() -> aiosqlite.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_match_id ON match_analyses(match_id);
        CREATE INDEX IF NOT EXISTS idx_share_id ON match_analyses(share_id);

        CREATE TABLE IF NOT EXISTS daily_quota (
            date TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.commit()
    await db.close()
