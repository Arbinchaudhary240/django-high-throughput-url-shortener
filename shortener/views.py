from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.core.cache import cache
from django.db import IntegrityError ,transaction
from django.db.models import F
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import logging

from .models import ShortURL, ClickAnalytics
from .serializers import ShortURLSerializer

CACHE_TTL = 60 * 60 * 24  #cache time limit 24 hrs in sec.
MAX_CREATE_ATTEMPTS = 5
logger = logging.getLogger(__name__)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])


def create_short_url(request):
    """
    API endpoint to generate a shortened URL.
    Payload: {"url": "https://example.com/long-url"}
    """
    original_url = request.data.get('url')

    if not original_url:
        return Response(
            {"detail": "URL is not required."}
        )

    #search in existing record if active short url already exist
    saved_link = ShortURL.objects.filter(
        original_url=original_url,
        is_active=True,
    ).first()

    is_created = False

    if saved_link is None:
        # Validating the input url once.
        serializer = ShortURLSerializer(data={'original_url': original_url})
        serializer.is_valid(raise_exception=True)

        for attempt in range(MAX_CREATE_ATTEMPTS):
            
            try:
                with transaction.atomic():
                    saved_link = serializer.save()

                is_created = True
                break

            except IntegrityError:
                # checks the existing record for using after integrity error 
                saved_link = ShortURL.objects.filter(
                    original_url=original_url,
                    is_active=True,
                ).first()

                if saved_link is not None:  #if found and stored in saved_link and saved_link is not none
                    break

                logger.warning(
                    "Short URL creation conflict. "
                    "Attempt %s/%s",
                    attempt + 1,
                    MAX_CREATE_ATTEMPTS,
                )

                if attempt == MAX_CREATE_ATTEMPTS - 1:
                    logger.exception("Failed to create short url after retries.")
                    raise

    if saved_link is None:
        return Response(
            {"detail": "Unable to create short url."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    
    # Pre-warm Redis cache key or creating redis key
    cache_key = f"url:{saved_link.short_code}"

    try:
        # storing original url in redis
        cache.set(cache_key, saved_link.original_url, timeout=CACHE_TTL)

    except Exception:
        logger.exception(
            "Redis cache update failed.",
            saved_link.short_code,
        )
    #combinig the current req domain and short code 
    full_short_url = request.build_absolute_uri(f"/r/{saved_link.short_code}")

    return Response({
        "short_code": saved_link.short_code,
        "original_url": saved_link.original_url,
        'short_url': full_short_url
    },status=(status.HTTP_201_CREATED if is_created else status.HTTP_200_OK),
    )


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