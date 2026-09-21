import json
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.core.cache import cache
from django.db.models import F
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import ShortURL, ClickAnalytics

CACHE_TTL = 60 * 60 * 24 


@csrf_exempt  # <-- REQUIRED: Allows Postman to send POST requests without CSRF blocks
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
            return JsonResponse({'error': 'URL is required'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    short_obj = ShortURL.objects.create(original_url=original_url)

    # Pre-warm Redis cache key
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
        # Cache hit: Fetch object directly by short_code
        short_obj = ShortURL.objects.filter(short_code=short_code, is_active=True).first()
        if not short_obj:
            return JsonResponse({'error': 'URL inactive or missing'}, status=404)
    else:
        # Cache miss: Query DB and populate cache
        short_obj = get_object_or_404(ShortURL, short_code=short_code, is_active=True)
        target_url = short_obj.original_url
        cache.set(cache_key, target_url, timeout=CACHE_TTL)

    # Atomic click count increment
    ShortURL.objects.filter(pk=short_obj.pk).update(clicks_count=F('clicks_count') + 1)

    # Extract visitor IP
    ip = request.META.get('HTTP_X_FORWARDED_FOR')
    if ip:
        ip = ip.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')

    # Log visitor analytics
    ClickAnalytics.objects.create(
        short_url=short_obj,
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        referrer=request.META.get('HTTP_REFERER', '')
    )

    return redirect(target_url)