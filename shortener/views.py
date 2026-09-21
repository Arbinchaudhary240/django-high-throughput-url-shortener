from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.cache import cache
from django.db.models import F
from django.views.decorators.http import require_http_methods
import json

from .models import ShortURL, ClickAnalytics

# Cache duration set to 24 hours (in seconds)
CACHE_TTL = 60 * 60 * 24


@require_http_methods(["POST"])
def create_short_url(request):
    """
    API endpoint to generate a shortened URL.
    Payload: {"url": "https://example.com/long-url"}
    """
    try:
        data = json.loads(request.body)
        original_url = data.get('url')
        if not original_url:
            return HttpResponseBadRequest(JsonResponse({'error': 'URL is required'}))
    except json.JSONDecodeError:
        return HttpResponseBadRequest(JsonResponse({'error': 'Invalid JSON'}))

    short_obj = ShortURL.objects.create(original_url=original_url)

    # Pre-warm Redis cache key immediately
    cache_key = f"url:{short_obj.short_code}"
    cache.set(cache_key, short_obj.original_url, timeout=CACHE_TTL)

    return JsonResponse({
        'short_code': short_obj.short_code,
        'original_url': short_obj.original_url,
        'short_url': request.build_absolute_uri(f'/r/{short_obj.short_code}')
    }, status=201)


def redirect_url(request, short_code):
    """
    Handles redirection with Redis Cache-Aside & atomic click tracking.
    """
    cache_key = f"url:{short_code}"
    target_url = cache.get(cache_key)

    if target_url:
        # CACHE HIT: Memory lookup succeeded, fetch object for log association
        short_obj = ShortURL.objects.filter(short_code=short_code, is_active=True).first()
        if not short_obj:
            return JsonResponse({'error': 'URL inactive or missing'}, status=404)
    else:
        # CACHE MISS: Query DB and update cache
        short_obj = get_object_or_404(ShortURL, short_code=short_code, is_active=True)
        target_url = short_obj.original_url
        cache.set(cache_key, target_url, timeout=CACHE_TTL)

    # 1. Atomic update prevents race conditions during high traffic
    ShortURL.objects.filter(pk=short_obj.pk).update(clicks_count=F('clicks_count') + 1)

    # 2. Extract visitor metadata
    ip = request.META.get('HTTP_X_FORWARDED_FOR')
    if ip:
        ip = ip.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')

    # Log visitor telemetry
    ClickAnalytics.objects.create(
        short_url=short_obj,
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        referrer=request.META.get('HTTP_REFERER', '')
    )

    # HTTP 302 ensures requests continue passing through the server for accurate analytics
    return redirect(target_url)