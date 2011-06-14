from django.conf.urls.defaults import *
from sisyphus.webapp.bughunter import views

urlpatterns = patterns('',
                       (r'^$', views.home),
                       (r'^crashtests/$', views.crashtests),
                       (r'^unittests/$', views.unittests),
                       (r'^admin/$', views.admin),
                       (r'^admin/workers/$', views.workers),
                       (r'^admin/workers/log/(\d*)/', views.worker_log),
                       (r'^api/admin/workers/$', views.workers_api),
                       (r'^api/admin/workersummary/$', views.admin),
                       (r'^post_files/$', views.post_files),
)
