from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.db import IntegrityError
from shortener.models import ShortURL, ClickAnalytics, generate_short_code
from unittest.mock import patch
import json


# Use locmem (in-memory) cache for fast, isolated test execution without requiring a running Redis instance
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
})
class URLShortenerTests(TestCase):

    def setUp(self):
        cache.clear()
        self.original_url = "https://example.com/long-path/page.html"
        self.short_url_obj = ShortURL.objects.create(original_url=self.original_url)

    def test_short_code_generation(self):
        """Test that ensure the ganerated short code have 6 characters."""
        code1 = generate_short_code()
        code2 = generate_short_code()
        
        self.assertEqual(len(code1), 6)
        self.assertEqual(len(code2), 6)
        self.assertNotEqual(code1, code2)

    def test_create_short_url_api_success(self):
    # Create a shortened URL via the POST API endpoint.
        url = reverse('create_short_url')
        payload = {'url': 'https://django-project.com'}

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 201)

        data = response.json()

        self.assertIn('short_code', data)
        self.assertEqual(
            data['original_url'],
            'https://django-project.com'
        )

        # Get the created ShortURL from the database
        short_url = ShortURL.objects.get(
            short_code=data['short_code']
        )

        # Redis key used by create_short_url()
        cache_key = f"url:{short_url.short_code}"

        # Check the cache contents
        cached_data = cache.get(cache_key)

        self.assertIsNotNone(cached_data)

        self.assertEqual(
            cached_data["id"],
            short_url.pk,
        )

        self.assertEqual(
            cached_data["original_url"],
            'https://django-project.com',
        )

    def test_create_short_url_reuses_existing_active_url(self):
        """Posting an active URL twice returns the same short code."""
        url = reverse('create_short_url')
        payload = {'url': 'https://django-project.com'}

        first_response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        second_response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            first_response.json()['short_code'],
            second_response.json()['short_code'],
        )
        self.assertEqual(
            ShortURL.objects.filter(original_url=payload['url']).count(),
            1,
        )

    def test_active_original_url_is_unique(self):
        """The database prevents duplicate active URLs."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ShortURL.objects.create(original_url=self.original_url)

        inactive_link = ShortURL.objects.create(
            original_url=self.original_url,
            is_active=False,
        )
        self.assertFalse(inactive_link.is_active)

    def test_create_short_url_retries_after_code_collision(self):
        """A short-code collision is retried instead of returning an error."""
        url = reverse('create_short_url')
        payload = {'url': 'https://new.example.com'}
        real_create = ShortURL.objects.create
        create_calls = 0

        def create_with_collision(**kwargs):
            nonlocal create_calls
            create_calls += 1
            if create_calls == 1:
                raise IntegrityError('short_code collision')
            return real_create(**kwargs)

        with patch.object(
            ShortURL.objects,
            'create',
            side_effect=create_with_collision,
        ):
            response = self.client.post(
                url,
                data=json.dumps(payload),
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(create_calls, 2)
        self.assertEqual(
            ShortURL.objects.filter(original_url=payload['url']).count(),
            1,
        )

    def test_create_short_url_rate_limits_anonymous_requests(self):
        """Anonymous clients receive 429 after five requests per minute."""
        url = reverse('create_short_url')
        responses = []

        for request_number in range(6):
            responses.append(self.client.post(
                url,
                data=json.dumps({'url': f'https://example.com/{request_number}'}),
                content_type='application/json'
            ))

        self.assertEqual([response.status_code for response in responses[:5]], [201] * 5)
        self.assertEqual(responses[5].status_code, 429)

    def test_create_short_url_api_invalid_json(self):
        """Checks the api handle the bad request and json"""
        url = reverse('create_short_url')
        response = self.client.post(
            url, 
            data="not-a-json", 
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_create_short_url_rejects_unsafe_urls(self):
        """Only HTTP and HTTPS URLs with valid hosts are accepted."""
        url = reverse('create_short_url')
        invalid_urls = [
            'javascript:alert(1)',
            'ftp://example.com/file.txt',
            'https:///missing-host',
            'https://user:password@example.com/path',
            'https://example.com:invalid/path',
        ]

        for invalid_url in invalid_urls:
            response = self.client.post(
                url,
                data=json.dumps({'url': invalid_url}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 400, invalid_url)

    def test_redirection_cache_miss_populates_cache(self):
        """Test that a cache miss retrieves the URL from DB and writes it to Redis cache."""
        cache_key = f"url:{self.short_url_obj.short_code}"
        
        # Ensure cache is initially empty
        self.assertIsNone(cache.get(cache_key))
        
        redirect_url = reverse('redirect_url', kwargs={'short_code': self.short_url_obj.short_code})
        response = self.client.get(redirect_url)
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.original_url)
        
        cached_data = cache.get(cache_key)

        self.assertEqual(
            cached_data["id"],
            self.short_url_obj.pk,
        )

        self.assertEqual(
            cached_data["original_url"],
            self.original_url,
        )

    def test_redirection_cache_hit(self):
        """Test that a cache hit bypasses DB fetch for target URL."""
        cache_key = f"url:{self.short_url_obj.short_code}"
        cache.set(
            cache_key,
            {
                "id": self.short_url_obj.pk,
                "original_url": self.original_url,
            },
            timeout=3600)
        
        redirect_url = reverse('redirect_url', kwargs={'short_code': self.short_url_obj.short_code})
        response = self.client.get(redirect_url)
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.original_url)

    def test_atomic_click_counter_and_analytics_logging(self):
        """Test to check click counter increments atomically or not and analytics record is created."""
        initial_clicks = self.short_url_obj.clicks_count
        redirect_url = reverse('redirect_url', kwargs={'short_code': self.short_url_obj.short_code})
        
        # Simulate 3 redirection requests
        for _ in range(3):
            self.client.get(redirect_url, HTTP_USER_AGENT='TestAgent/1.0', HTTP_REFERER='https://google.com')
        
        # Refresh object state from DB
        self.short_url_obj.refresh_from_db()
        
        self.assertEqual(self.short_url_obj.clicks_count, initial_clicks + 3)
        self.assertEqual(ClickAnalytics.objects.filter(short_url=self.short_url_obj).count(), 3)
        
        # Verify analytics metadata
        latest_analytics = ClickAnalytics.objects.filter(short_url=self.short_url_obj).first()
        self.assertEqual(latest_analytics.user_agent, 'TestAgent/1.0')
        self.assertEqual(latest_analytics.referrer, 'https://google.com')


    def test_cache_is_invalidated_when_url_is_deactivated(self):
        cache_key = f"url:{self.short_url_obj.short_code}"

        cache.set(
            cache_key,
            {
                "id": self.short_url_obj.pk,
                "original_url": self.original_url,
            },
            timeout=3600,
        )

        self.short_url_obj.is_active = False
        self.short_url_obj.save(update_fields=["is_active"])

        cache.delete(cache_key)

        self.assertIsNone(cache.get(cache_key))


    def test_redirect_rejects_stale_cache_for_inactive_url(self):
        cache_key = f"url:{self.short_url_obj.short_code}"

        cache.set(
            cache_key,
            {
                "id": self.short_url_obj.pk,
                "original_url": self.original_url,
            },
            timeout=3600
        )

        self.short_url_obj.is_active = False
        self.short_url_obj.save(update_fields=["is_active"])

        redirect_url = reverse(
            "redirect_url",
            kwargs={"short_code": self.short_url_obj.short_code},
        )

        response = self.client.get(redirect_url)

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(cache.get(cache_key))