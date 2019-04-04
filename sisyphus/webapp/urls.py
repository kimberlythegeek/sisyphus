from django.conf.urls import url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin, admindocs
admin.autodiscover()

urlpatterns = [
    url(r'^djangoadmin/doc/', admindocs.urls),
    url(r'^djangoadmin/', admin.site.urls),
    url(r'^bughunter/', urls)
]
