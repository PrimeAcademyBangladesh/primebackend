"""
Footer serializers

Serializers for the footer models used by the public footer API. These
serializers provide nested representations of link groups and social
links and include small convenience fields such as `logo_url` and the
current copyright year.
"""

from typing import Optional

from rest_framework import serializers

from api.models.models_footer import Footer, LinkGroup, QuickLink, SocialLink


class QuickLinkSerializer(serializers.ModelSerializer):
    """Serializer for a single quick link used in footer link groups.

    Provides a compact representation suitable for frontend consumption.
    """

    class Meta:
        model = QuickLink
        fields = ("label", "url", "is_external", "order")


class LinkGroupSerializer(serializers.ModelSerializer):
    """Serializer for a footer column which contains quick links.

    The `links` nested serializer serializes the set of QuickLink items
    attached to the group.
    """

    links = QuickLinkSerializer(many=True)

    class Meta:
        model = LinkGroup
        fields = ("title", "order", "links")


class SocialLinkSerializer(serializers.ModelSerializer):
    """Serializer for social link entries (platform + URL).

    Used to render social icons with ordered links in the footer.
    """

    class Meta:
        model = SocialLink
        fields = ("platform", "url", "order")


class FooterSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    link_groups = LinkGroupSerializer(many=True)
    social_links = SocialLinkSerializer(many=True)
    copyright_year = serializers.SerializerMethodField()

    class Meta:
        model = Footer
        fields = (
            "logo_url",
            "description",
            "address",
            "email",
            "phone",
            "link_groups",
            "social_links",
            "copyright_name",
            "copyright_year",
            "updated_at",
        )

    # ---------------------------
    # Read helpers
    # ---------------------------
    def get_logo_url(self, obj) -> Optional[str]:
        request = self.context.get("request")
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return obj.logo.url if obj.logo else None

    def get_copyright_year(self, obj) -> int:
        from datetime import date
        return date.today().year

    # ---------------------------
    # Write helpers
    # ---------------------------
    def create(self, validated_data):
        link_groups_data = validated_data.pop("link_groups", [])
        social_links_data = validated_data.pop("social_links", [])

        footer = Footer.objects.create(**validated_data)

        # link groups + nested links
        for group_data in link_groups_data:
            links_data = group_data.pop("links", [])
            group = LinkGroup.objects.create(footer=footer, **group_data)
            for link_data in links_data:
                QuickLink.objects.create(group=group, **link_data)

        # social links
        for social_data in social_links_data:
            SocialLink.objects.create(footer=footer, **social_data)

        return footer

    def update(self, instance, validated_data):
        link_groups_data = validated_data.pop("link_groups", None)
        social_links_data = validated_data.pop("social_links", None)

        # Update footer base fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Replace link groups if provided
        if link_groups_data is not None:
            instance.link_groups.all().delete()
            for group_data in link_groups_data:
                links_data = group_data.pop("links", [])
                group = LinkGroup.objects.create(footer=instance, **group_data)
                for link_data in links_data:
                    QuickLink.objects.create(group=group, **link_data)

        # Replace social links if provided
        if social_links_data is not None:
            instance.social_links.all().delete()
            for social_data in social_links_data:
                SocialLink.objects.create(footer=instance, **social_data)

        return instance

