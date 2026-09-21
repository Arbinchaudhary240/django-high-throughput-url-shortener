from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache
from django.db.models import F
from shortener.models import ShortURL, ClickAnalytics, generate_short_code
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
        """Ceating a shortened URL via the POST API endpoint."""
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
        self.assertEqual(data['original_url'], 'https://django-project.com')
        
        cached_url = cache.get(f"url:{data['short_code']}")
        self.assertEqual(cached_url, 'https://django-project.com')

    def test_create_short_url_api_invalid_json(self):
        """Checks the api handle the bad request and json"""
        url = reverse('create_short_url')
        response = self.client.post(
            url, 
            data="not-a-json", 
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_redirection_cache_miss_populates_cache(self):
        """Test that a cache miss retrieves the URL from DB and writes it to Redis cache."""
        cache_key = f"url:{self.short_url_obj.short_code}"
        
        # Ensure cache is initially empty
        self.assertIsNone(cache.get(cache_key))
        
        redirect_url = reverse('redirect_url', kwargs={'short_code': self.short_url_obj.short_code})
        response = self.client.get(redirect_url)
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.original_url)
        
       
        self.assertEqual(cache.get(cache_key), self.original_url)

    def test_redirection_cache_hit(self):
        """Test that a cache hit bypasses DB fetch for target URL."""
        cache_key = f"url:{self.short_url_obj.short_code}"
        cache.set(cache_key, self.original_url, timeout=3600)
        
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