from redis import Redis

from app.core.settings import get_settings

settings = get_settings()
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def redis_ready() -> bool:
    try:
        return bool(redis_client.ping())
    except Exception:
        return False
