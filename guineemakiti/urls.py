from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from boutique.sitemaps import ProductSitemap, StaticPageSitemap

sitemaps = {
    "products": ProductSitemap,
    "static": StaticPageSitemap,
}

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("google10babad53f3eade7.html", TemplateView.as_view(template_name="google10babad53f3eade7.html", content_type="text/html")),
    path("", include("boutique.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
