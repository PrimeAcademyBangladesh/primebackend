from rest_framework import serializers

from api.models.models_seo import PageSEO


class PageSEOSerializer(serializers.ModelSerializer):
    """Serializer for complete SEO data - WITHOUT duplication"""
    
    class Meta:
        model = PageSEO
        fields = [
            'id', 'page_name', 
            # Basic SEO
            'meta_title', 'meta_description', 'meta_keywords',
            # Open Graph
            'og_title', 'og_description', 'og_image', 'og_type', 'og_url',
            # Twitter Card
            'twitter_card', 'twitter_title', 'twitter_description', 'twitter_image', 
            'twitter_site', 'twitter_creator',
            # Advanced SEO
            'canonical_url', 'robots_meta', 'structured_data',
            # Timestamps
            'created_at', 'updated_at',
            'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        
    def get_structured_data(self, obj):
        """Return the dynamic structured data"""
        return obj.structured_data 


class PageSEOCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating SEO data"""
    
    class Meta:
        model = PageSEO
        fields = [
            'page_name',
            # Basic SEO
            'meta_title', 'meta_description', 'meta_keywords',
            # Open Graph
            'og_title', 'og_description', 'og_image', 'og_type', 'og_url',
            # Twitter Card
            'twitter_card', 'twitter_title', 'twitter_description', 'twitter_image', 
            'twitter_site', 'twitter_creator',
            # Advanced SEO
            'canonical_url', 'robots_meta', 'structured_data',
            'is_active'
        ]
    
    def validate_page_name(self, value):
        """Ensure page_name is lowercase and URL-friendly"""
        return value.lower().strip()


class PageSEOMetaSerializer(serializers.ModelSerializer):
    """Serializer specifically for frontend meta data (React Helmet)"""
    seo_meta = serializers.SerializerMethodField()
    
    class Meta:
        model = PageSEO
        fields = ['seo_meta']
    
    def get_seo_meta(self, obj):
        return obj.get_seo_meta()