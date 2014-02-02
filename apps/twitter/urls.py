# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url, include
from views import DashboardView, DeleteScheduleOrderView
from wizards import CreateOrderWizard, FORMS

urlpatterns = patterns('',
                       url(r'^$', DashboardView.as_view(), name='twitter-home'),
                       url(r'^create-order/$', CreateOrderWizard.as_view(FORMS),
                           name='twitter-create-order'),
                       url(r'^delete/(?P<pk>[-\w]+)/$', DeleteScheduleOrderView.as_view(), name='twitter-delete'),
)