from django.conf.urls.defaults import *

urlpatterns = patterns('matgendb.webui.home.views',
    # regex are retarded and python is stupid
    # thank you for those words of wisdom, Michael
    (r'^$', 'index'),
    (r'^query$', 'query')
)
