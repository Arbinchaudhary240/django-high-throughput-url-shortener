from rest_framework import serializers
from urllib.parse import urlsplit

from .models import ShortURL


class ShortURLSerializer(serializers.ModelSerializer):
    def validate_original_url(self, value):
        parsed_url = urlsplit(value)

        if parsed_url.scheme.lower() not in {'http', 'https'}:
            raise serializers.ValidationError('Only HTTP and HTTPS URLs are allowed.')

        if not parsed_url.netloc or not parsed_url.hostname:
            raise serializers.ValidationError('The URL must include a valid hostname.')

        try:
            parsed_url.port
        except ValueError as error:
            raise serializers.ValidationError(
                'The URL contains an invalid port.'
            ) from error

        if parsed_url.username or parsed_url.password:
            raise serializers.ValidationError(
                'URLs must not contain embedded credentials.'
            )

        return value

    class Meta:
        model = ShortURL
        fields = ('short_code', 'original_url')
        read_only_fields = ('short_code',)