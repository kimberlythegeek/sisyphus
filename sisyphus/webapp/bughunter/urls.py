from django.conf.urls import patterns, url, include

from sisyphus.webapp.bughunter import views

# FIXME: We should have a generic parameter handler, e.g. for start/end dates
urlpatterns = patterns('',
                       (r'^$', views.bhview),
                       (r'^crashtests/$', views.crashtests),
                       (r'^unittests/$', views.unittests),
                       (r'^login/$', views.view_login),
                       (r'^logout/$', views.view_logout),
                       (r'^views/$', views.bhview),
                       (r'^views/help/.*$', views.get_help),
                       (r'^views/get_date_range$', views.get_date_range),
                       (r'^api/views/.*$', views.get_bhview),
                       (r'^api/resubmit/.*$', views.resubmit_urls),

                       (r'^api/login/$', views.log_in),
                       (r'^api/logout/$', views.log_out),
                       (r'^api/admin/workers/$', views.workers_api),
                       (r'^api/admin/workersummary/$', views.worker_summary),
                       (r'^api/admin/workers/log/([^/]*)/([^/]*)/$', views.all_workers_log_api),
                       (r'^api/admin/workers/(\d*)/$', views.worker_api),
                       (r'^api/admin/workers/(\d*)/log/([^/]*)/([^/]*)/$',
                        views.worker_log_api),
                       (r'^post_files/$', views.post_files),
                       (r'^api/crashes_by_date/([^/]*)/([^/]*)/(.*)$', views.crashes_by_date),
)
