from django.db import models
import string
import secrets

def generate_short_code():
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(6))

class ShortURL(models.Model):
    orignal_url = models.URLField(max_length=2048)
    short_code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        default=generate_short_code
    )
    created_at = models.DateTimeField(auto_now_add=True)
    clicks_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.short_code} -> {self.orignal_url[:30]}"


class ClickAnalytics(models.Model):
    short_url = models.ForeignKey(
        ShortURL,
        on_delete=models.CASCADE,
        related_name='analytics'
    )
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    referrer = models.URLField(max_length=2048, blank=True, default='')

    class Meta:
        ordering = ['-clicked_at']