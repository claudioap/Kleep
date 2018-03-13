from django.conf.urls import url

from api import views

urlpatterns = [
    # url(r'^', include(router.urls)),
    # url(r'^profile/(?P<nickname>\w+)/$', None),
    url(r'^buildings/$', views.BuildingList.as_view()),
    # url(r'^building/(?P<pk>[0-9]+)/$', None),
    # url('', GroupViewSet),
    url(r'^bars/$', views.BarList.as_view()),
    url(r'^services/$', views.ServiceList.as_view()),
    url(r'^departments/$', views.DepartmentList.as_view()),
    url(r'^department/(?P<pk>[0-9]+)/$', views.DepartmentDetailed.as_view()),
    url(r'^course/(?P<pk>[0-9]+)/$', views.CourseDetailed.as_view()),
    url(r'^class/(?P<pk>[0-9]+)/$', views.ClassDetailed.as_view()),
    url(r'^news/$', views.NewsList.as_view()),
    url(r'^news/(?P<pk>[0-9]+)/$', views.News.as_view()),
    # url(r'^articles/$', None),
    # url(r'^groups/$', None),
    # url(r'^menus/$', None),
    url(r'^synopsis_areas/$', views.SyopsesAreas.as_view()),
    url(r'^synopsis_topic/(?P<pk>[0-9]+)/$', views.SyopsesTopicSections.as_view()),
    # url(r'^store/$', None),
    # url(r'^classified/$', None),
    # url(r'^events/$', None),
    url(r'^campus_map/$', views.CampusMap.as_view()),
    # url(r'^transportation_map/$', None),
]
