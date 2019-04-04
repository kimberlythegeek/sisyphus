from django.conf.urls import url

from . import views

# FIXME: We should have a generic parameter handler, e.g. for start/end dates
urlpatterns = [
   url(r'^$', views.bhview),
   url(r'^crashtests/$', views.crashtests),
   url(r'^unittests/$', views.unittests),
   url(r'^login/$', views.view_login),
   url(r'^logout/$', views.view_logout),
   url(r'^views/$', views.bhview),
   url(r'^views/help/.*$', views.get_help),
   url(r'^views/get_date_range$', views.get_date_range),
   url(r'^api/views/.*$', views.get_bhview),
   url(r'^api/resubmit/.*$', views.resubmit_urls),

   url(r'^api/login/$', views.log_in),
   url(r'^api/logout/$', views.log_out),
   url(r'^api/admin/workers/$', views.workers_api),
   url(r'^api/admin/workersummary/$', views.worker_summary),
   url(r'^api/admin/workers/log/([^/]*)/([^/]*)/$', views.all_workers_log_api),
   url(r'^api/admin/workers/(\d*)/$', views.worker_api),
   url(r'^api/admin/workers/(\d*)/log/([^/]*)/([^/]*)/$',
    views.worker_log_api),
   url(r'^post_files/$', views.post_files),
   url(r'^api/crashes_by_date/([^/]*)/([^/]*)/(.*)$', views.crashes_by_date),
]
