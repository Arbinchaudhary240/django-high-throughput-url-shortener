from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.core.cache import cache
from django.db.models import F
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import ShortURL, ClickAnalytics
from .serializers import ShortURLSerializer

CACHE_TTL = 60 * 60 * 24  #cache time limit 24 hrs in sec.


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])


def create_short_url(request):
    """
    API endpoint to generate a shortened URL.
    Payload: {"url": "https://example.com/long-url"}
    """
    serializer = ShortURLSerializer(data={'original_url': request.data.get('url')})
    serializer.is_valid(raise_exception=True)

    saved_link = serializer.save()

    # Pre-warm Redis cache key
    cache_key = f"url:{saved_link.short_code}"
    cache.set(cache_key, saved_link.original_url, timeout=CACHE_TTL)

    full_short_url = request.build_absolute_uri(f'/r/{saved_link.short_code}')
    return Response({
        "short_code": saved_link.short_code,
        "original_url": saved_link.original_url,
        'short_url': full_short_url
    }, status=status.HTTP_201_CREATED)


def redirect_url(request, short_code):
    """
    Handles redirection with Redis Cache-Aside & atomic click tracking.
    """
    cache_key = f"url:{short_code}"
    target_url = cache.get(cache_key)

    if target_url:
        # Cache hit: Fetch object directly by short_code
        url_code = ShortURL.objects.filter(short_code=short_code, is_active=True).first()
        if not url_code:
            return JsonResponse({'error': 'URL inactive or missing'}, status=404)
    else:
        # Cache miss: Query DB and populate cache
        url_code = get_object_or_404(ShortURL, short_code=short_code, is_active=True)
        target_url = url_code.original_url
        cache.set(cache_key, target_url, timeout=CACHE_TTL)

    #increase the click count by 1
    ShortURL.objects.filter(pk=url_code.pk).update(clicks_count=F('clicks_count') + 1)

    # Extract visitor IP
    ip = request.META.get('HTTP_X_FORWARDED_FOR')
    if ip:
        visitor_ip = ip.split(',')[0].strip()
    else:
        visitor_ip = request.META.get('REMOTE_ADDR')

    # Log visitor analytics
    ClickAnalytics.objects.create(
        short_url=url_code,
        ip_address=visitor_ip,
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        referrer=request.META.get('HTTP_REFERER', '')
    )

    return redirect(target_url)