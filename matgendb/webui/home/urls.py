from django.conf.urls import *

urlpatterns = patterns('matgendb.webui.home.views',
    (r'^$', 'index'),
    (r'^query$', 'query')
)
