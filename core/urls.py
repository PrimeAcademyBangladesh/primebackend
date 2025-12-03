"""Root URL configuration for the Django project.

Includes admin site and API app routes.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.utils.decorators import method_decorator
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


@method_decorator(login_required(login_url="/admin/login/"), name="dispatch")
class ProtectedSchemaView(SpectacularAPIView):
    pass

@method_decorator(login_required(login_url="/admin/login/"), name="dispatch")
class ProtectedSwaggerView(SpectacularSwaggerView):
    pass

urlpatterns = [
    path('admin/', admin.site.urls),
    path('_nested_admin/', include('nested_admin.urls')),

    path('api/', include('api.urls')),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    # API schema and documentation
    path("schema/", ProtectedSchemaView.as_view(), name="schema"),
    path("api/docs/", ProtectedSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# In development serve media files through Django
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    