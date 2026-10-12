from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite+pysqlite:///./cloudmorph.db")
    cors_origins: tuple[str, ...] = tuple(
        x.strip()
        for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if x.strip()
    )
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    seed: int = int(os.getenv("CLOUDMORPH_SEED", "42"))


settings = Settings()
