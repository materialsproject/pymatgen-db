from django.conf.urls import *

urlpatterns = patterns('matgendb.webui.rest.views',
    (r'^/query$', 'query'),
    (r'^(?P<rest_query>.*)$', 'index'),
)
