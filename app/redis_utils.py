import os
import redis
import json
from typing import Any, Optional, Union, Dict
from contextlib import contextmanager
import logging

logger = logging.getLogger("aed_api.redis")

# Get Redis configuration from environment variables
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
CACHE_TTL = int(os.environ.get("CACHE_TTL", 3600))  # Default: 1 hour

# Create Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
)

@contextmanager
def redis_connection():
    """Context manager for Redis connections with error handling"""
    try:
        yield redis_client
    except redis.exceptions.ConnectionError as e:
        logger.warning(f"Redis connection error: {str(e)}")
        yield None
    except Exception as e:
        logger.error(f"Redis error: {str(e)}")
        yield None

def is_redis_available() -> bool:
    """Check if Redis is available"""
    try:
        return redis_client.ping()
    except Exception:
        return False

def get_cache(key: str) -> Optional[Any]:
    """Get data from Redis cache"""
    with redis_connection() as r:
        if not r:
            return None
        
        try:
            data = r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting cache for {key}: {str(e)}")
            return None

def set_cache(key: str, data: Any, ttl: int = None) -> bool:
    """Set data in Redis cache"""
    if ttl is None:
        ttl = CACHE_TTL
        
    with redis_connection() as r:
        if not r:
            return False
        
        try:
            serialized_data = json.dumps(data)
            return r.setex(key, ttl, serialized_data)
        except Exception as e:
            logger.error(f"Error setting cache for {key}: {str(e)}")
            return False

def delete_cache(key: str) -> bool:
    """Delete data from Redis cache"""
    with redis_connection() as r:
        if not r:
            return False
        
        try:
            return r.delete(key) > 0
        except Exception as e:
            logger.error(f"Error deleting cache for {key}: {str(e)}")
            return False

def delete_pattern(pattern: str) -> int:
    """Delete all keys matching pattern"""
    with redis_connection() as r:
        if not r:
            return 0
        
        try:
            keys = r.keys(pattern)
            if keys:
                return r.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error deleting pattern {pattern}: {str(e)}")
            return 0

def create_cache_key(*args) -> str:
    """Create a cache key from multiple arguments"""
    return ":".join(str(arg) for arg in args if arg is not None)

def get_stats() -> Dict[str, Union[int, str, bool]]:
    """Get Redis stats for monitoring"""
    stats = {
        "available": False,
        "keys": 0,
        "used_memory": "N/A",
        "used_memory_human": "N/A",
    }
    
    with redis_connection() as r:
        if not r:
            return stats
        
        try:
            info = r.info()
            stats.update({
                "available": True,
                "keys": r.dbsize(),
                "used_memory": info.get("used_memory", "N/A"),
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", "N/A"),
                "uptime_in_seconds": info.get("uptime_in_seconds", "N/A"),
            })
            return stats
        except Exception as e:
            logger.error(f"Error getting Redis stats: {str(e)}")
            return stats
