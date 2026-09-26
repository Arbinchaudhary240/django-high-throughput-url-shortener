from django.core.cache import cache

def get_url_cache_key(short_code):
    return f"url:{short_code}"


def invalidate_short_url_cache(short_code):
    cache.delete(get_url_cache_key(short_code))