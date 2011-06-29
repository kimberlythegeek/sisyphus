from django.conf.urls.defaults import *
from sisyphus.webapp.bughunter import views

urlpatterns = patterns('',
                       (r'^$', views.home),
                       (r'^crashtests/$', views.crashtests),
                       (r'^unittests/$', views.unittests),
                       (r'^api/admin/workers/$', views.workers_api),
                       (r'^api/admin/workersummary/$', views.worker_summary),
                       (r'^api/admin/workers/log/([^/]*)/([^/]*)/$', views.all_workers_log_api),
                       (r'^api/admin/workers/(\d*)/$', views.worker_api),
                       (r'^api/admin/workers/(\d*)/log/([^/]*)/([^/]*)/$',
                        views.worker_log_api),
                       (r'^post_files/$', views.post_files),
)
