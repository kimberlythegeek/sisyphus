from django.conf.urls import patterns, url, include

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',

    (r'^djangoadmin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^djangoadmin/', include(admin.site.urls)),

    (r'^bughunter/', include('sisyphus.webapp.bughunter.urls')),

)
