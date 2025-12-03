import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils.text import slugify

from api.models.images_base_class import OptimizedImageModel
from api.utils.helper_models import TimeStampedModel


class BaseSEOModel(TimeStampedModel, OptimizedImageModel):
    """
    Abstract base model for SEO meta data.
    Manages all SEO tags and generates structured data.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for this SEO configuration."
    )

    # Page Identification
    page_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="✅ Unique page identifier (max 100 chars). Use lowercase, URL-friendly names like 'home', 'about-us'.",
    )

    # Basic SEO Meta
    meta_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Title tag for search results (max 200 chars, keep under 60). Example: 'Prime Academy - Best Online Courses'",
    )
    meta_description = models.TextField(
        max_length=300,
        blank=True,
        help_text="Description in search results (max 300 chars, keep 150-160). Your 'ad copy' for Google.",
    )
    meta_keywords = models.TextField(
        blank=True,
        help_text="Comma-separated keywords. Less important for Google now, but can be useful.",
    )

    # Open Graph (Facebook, LinkedIn)
    og_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Title for social media shares (max 200 chars). Will use Meta Title if empty.",
    )
    og_description = models.TextField(
        max_length=300,
        blank=True,
        help_text="Description for social media (max 300 chars). Will use Meta Description if empty.",
    )
    og_image = models.ImageField(
        upload_to="seo/og_images/",
        blank=True,
        null=True,
        help_text="Image for social shares. Recommended: 1200x630 pixels.",
    )
    
    og_type = models.CharField(
        max_length=50,
        default="website",
        choices=[
            ("website", "Website"),
            ("article", "Article"),
            ("product", "Product"),
        ],
        help_text="Content type (max 50 chars). 'website' for most pages, 'article' for blog posts.",
    )
    og_url = models.URLField(
        blank=True,
        help_text="Permanent URL of the page. Will use Canonical URL if empty.",
    )

    # Twitter Card
    twitter_card = models.CharField(
        max_length=50,
        default="summary_large_image",
        choices=[
            ("summary", "Summary"),
            ("summary_large_image", "Large Summary"),
            ("app", "App"),
            ("player", "Player"),
        ],
        help_text="Card type (max 50 chars). 'Summary with Large Image' is usually best.",
    )
    twitter_title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Title for Twitter (max 200 chars). Will use OG Title if empty.",
    )
    twitter_description = models.TextField(
        max_length=300,
        blank=True,
        help_text="Description for Twitter (max 300 chars). Will use OG Description if empty",
    )
    twitter_image = models.ImageField(
        upload_to="seo/twitter_images/",
        blank=True,
        null=True,
        help_text="Image for Twitter. Recommended: 1200x600 pixels.",
    )
    twitter_site = models.CharField(
        max_length=100,
        blank=True,
        help_text="Your site's Twitter handle (max 100 chars), e.g., '@PrimeAcademy'.",
    )
    twitter_creator = models.CharField(
        max_length=100,
        blank=True,
        help_text="Author's Twitter handle (max 100 chars), e.g., '@AuthorName'.",
    )

    # Additional SEO
    canonical_url = models.URLField(
        blank=True,
        help_text="The single, official URL for this page to prevent duplicate content issues.",
    )
    robots_meta = models.CharField(
        max_length=100,
        blank=True,
        default="index, follow",
        choices=[
            ("index, follow", "✅ Index, Follow (Recommended)"),
            ("noindex, follow", "🚫 NoIndex, Follow"),
            ("index, nofollow", "✅ Index, 🚫 NoFollow"),
            ("noindex, nofollow", "🚫 NoIndex, 🚫 NoFollow"),
        ],
        help_text="Search engine crawler instructions (max 100 chars).",
    )

    # Structured Data (JSON-LD)
    structured_data = models.JSONField(
        blank=True,
        null=True,
        help_text="🧠 JSON-LD data. Leave empty to auto-generate on save. You can also paste your custom JSON-LD here to override it.",
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to disable this SEO configuration."
    )
    
    
    IMAGE_FIELDS_OPTIMIZATION = {
        'og_image': {
            'max_size': (800, 800),
            'min_size': (400, 400),
            'max_bytes': 300*1024,
            'min_bytes': 100*1024,
            'max_upload_mb': 2
        },
        'twitter_image': {
            'max_size': (800, 800),
            'min_size': (400, 400),
            'max_bytes': 300*1024,
            'min_bytes': 100*1024,
            'max_upload_mb': 2
        }
    }

    class Meta:
        abstract = True
        ordering = ["page_name"]

    def __str__(self):
        return f"SEO - {self.page_name}"

    def clean(self):
        if self.page_name:
            self.page_name = slugify(self.page_name)
        # Normalize canonical_url: if it's a path or lacks scheme, join with FRONTEND_URL
        if self.canonical_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(self.canonical_url)
                if not parsed.scheme:
                    base = settings.FRONTEND_URL.rstrip('/')
                    path = self.canonical_url
                    if not path.startswith('/'):
                        path = '/' + path
                    self.canonical_url = f"{base}{path}"
            except Exception:
                # Be defensive: leave canonical_url unchanged on unexpected errors
                pass

        # Validate structured_data if provided: must be a JSON object with
        # at least '@context' and '@type' keys to be considered valid JSON-LD.
        if self.structured_data:
            try:
                from django.core.exceptions import ValidationError
                if not isinstance(self.structured_data, dict):
                    raise ValidationError({
                        'structured_data': 'Structured data must be a JSON object/dictionary.'
                    })

                # Basic JSON-LD presence checks
                if '@context' not in self.structured_data or '@type' not in self.structured_data:
                    raise ValidationError({
                        'structured_data': "Structured data must include '@context' and '@type' keys."
                    })
            except ValidationError:
                # Re-raise so callers (admin/forms/save) get a proper ValidationError
                raise
            except Exception:
                # Any unexpected parsing errors: be defensive and raise a ValidationError
                from django.core.exceptions import ValidationError
                raise ValidationError({'structured_data': 'Invalid structured_data format.'})

        super().clean()

    def save(self, *args, **kwargs):
        self.clean()

        # OPTIMIZED: Auto-populate empty fields from better sources
        fallbacks = {
            "og_title": self.meta_title,
            "og_description": self.meta_description,
            "og_url": self.canonical_url,
            "twitter_title": self.og_title or self.meta_title,
            "twitter_description": self.og_description or self.meta_description,
            "twitter_image": self.og_image,
            "twitter_site": settings.SEO_CONFIG.get("DEFAULT_TWITTER_SITE", ""),
        }
        for field, fallback in fallbacks.items():
            if not getattr(self, field) and fallback:
                setattr(self, field, fallback)

        # BRILLIANT WAY: Auto-generate structured_data if the field is empty
        if not self.structured_data:
            self.structured_data = self._generate_base_structured_data()

        super().save(*args, **kwargs)
        # OPTIMIZATION: Clear cache for this object whenever it's saved
        cache.delete(f"seo_meta_{self.pk}")

    def get_seo_meta(self, request=None):
        """
        Return complete SEO meta data as a cached dictionary.
        Accepts a request object to build full absolute URLs for images.
        """
        cache_key = f"seo_meta_{self.pk}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        # Helper to build full URLs like https://.../media/image.jpg
        def build_absolute_uri(image_field):
            if not image_field:
                return None
            if request:
                return request.build_absolute_uri(image_field.url)
            return f"{settings.FRONTEND_URL}{image_field.url}"

        # If structured_data is unset, synthesize it on-the-fly so callers
        # (including frontend) always receive a usable JSON-LD object even
        # for unsaved or legacy records.
        structured = self.structured_data or self._generate_base_structured_data()

        data = {
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "meta_keywords": self.meta_keywords,
            "robots_meta": self.robots_meta,
            "canonical_url": self.canonical_url,
            "og_title": self.og_title,
            "og_description": self.og_description,
            "og_image": build_absolute_uri(self.og_image),
            "og_type": self.og_type,
            "og_url": self.og_url,
            "twitter_card": self.twitter_card,
            "twitter_title": self.twitter_title,
            "twitter_description": self.twitter_description,
            "twitter_image": build_absolute_uri(self.twitter_image),
            "twitter_site": self.twitter_site,
            "twitter_creator": self.twitter_creator,
            "structured_data": structured,
        }

        # Cache the result for 1 hour
        cache.set(cache_key, data, timeout=3600)
        return data

    def _get_organization_info(self):
        """Helper to generate Organization schema from settings."""
        return {
            "@type": "Organization",
            "name": settings.SEO_CONFIG.get("SITE_NAME"),
            "url": settings.FRONTEND_URL,
            "logo": {
                "@type": "ImageObject",
                "url": settings.SEO_CONFIG.get("ORGANIZATION_LOGO_URL"),
            },
            "sameAs": settings.SEO_CONFIG.get("ORGANIZATION_SOCIAL_PROFILES", []),
        }

    def _generate_base_structured_data(self):
        """Generates the base JSON-LD for a static page."""
        base_url = self.canonical_url or f"{settings.FRONTEND_URL}/{self.page_name}/"

        data = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": self.meta_title or self.page_name.replace("-", " ").title(),
            "description": self.meta_description,
            "url": base_url,
            "publisher": self._get_organization_info(),
            "breadcrumb": {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": settings.FRONTEND_URL,
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": self.page_name.replace("-", " ").title(),
                        "item": base_url,
                    },
                ],
            },
        }
        # If this is the About page, optimize JSON-LD to include rich Organization info
        try:
            about_slugs = {"about", "about-us", "about_us", "aboutus"}
            if (self.page_name and self.page_name.lower() in about_slugs) or (self.meta_title and self.meta_title.lower().startswith("about")):
                # Use AboutPage type and include organization as mainEntity for richer markup
                data["@type"] = "AboutPage"
                org = self._get_organization_info()
                # optionally attach founding/founders/contact if present in settings.SEO_CONFIG
                extra = {}
                fd = settings.SEO_CONFIG.get("FOUNDING_DATE")
                if fd:
                    extra["foundingDate"] = fd
                founders = settings.SEO_CONFIG.get("FOUNDERS")
                if founders:
                    # expect a list of names
                    extra["founders"] = [{"@type": "Person", "name": n} for n in founders]
                contact = settings.SEO_CONFIG.get("ORGANIZATION_CONTACT")
                if contact:
                    # contact expected to be dict with telephone/email
                    extra["contactPoint"] = contact
                if extra:
                    org = {**org, **extra}
                data["mainEntity"] = org
        except Exception:
            # continue gracefully if any settings are missing
            pass

        # Try to include FAQ structured data when there are active FAQ items
        try:
            from django.utils.html import strip_tags

            from api.models.models_faq import FAQ

            faqs = FAQ.objects.filter(is_active=True, item__faq_nav_slug=self.page_name)
            if not faqs.exists():
                # fallback: match by raw faq_nav text
                faqs = FAQ.objects.filter(is_active=True, item__faq_nav__iexact=self.page_name)

            if faqs.exists():
                questions = []
                for faq in faqs.order_by('item__faq_nav', 'order'):
                    q_text = strip_tags(faq.question or '')
                    a_text = strip_tags(faq.answer or '')
                    if q_text and a_text:
                        questions.append({
                            "@type": "Question",
                            "name": q_text,
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": a_text,
                            },
                        })

                if questions:
                    # Per schema.org, include FAQ as mainEntity on the WebPage
                    data["mainEntity"] = {
                        "@type": "FAQPage",
                        "mainEntity": questions,
                    }
        except Exception:
            # Be defensive: if FAQ model isn't available or query fails, skip FAQ inclusion
            pass

        return data


class PageSEO(BaseSEOModel):
    """Concrete SEO model for your static pages like 'home', 'about', etc."""

    class Meta(BaseSEOModel.Meta):
        verbose_name = "Page SEO"
        verbose_name_plural = "Page SEOs"

    def get_absolute_url(self):
        return f"/{self.page_name}/"
