from rest_framework import serializers
from urllib.parse import urlsplit

from .models import ShortURL


class ShortURLSerializer(serializers.ModelSerializer):
    def validate_original_url(self, value):
        parsed_url = urlsplit(value)

        if parsed_url.scheme.lower() not in {'http', 'https'}:
            raise serializers.ValidationError('Only HTTP and HTTPS URLs are allowed.')

        try:
            hostname = parsed_url.hostname
            parsed_url.port
        except ValueError as error:
            raise serializers.ValidationError(
                'The URL contains an invalid host or port.'
            ) from error

        if not parsed_url.netloc or not hostname:
            raise serializers.ValidationError(
                'The URL must include a valid hostname.'
            )

        if parsed_url.username or parsed_url.password:
            raise serializers.ValidationError(
                'URLs must not contain embedded credentials.'
            )

        return value

    class Meta:
        model = ShortURL
        fields = ('short_code', 'original_url')
        read_only_fields = ('short_code',)