# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.urls import path
from apps.ipam import views

urlpatterns = [
    path('subnet/', views.SubnetView.as_view()),
    path('subnet/<int:subnet_id>/addresses/', views.get_subnet_addresses),
    path('address/allocate/', views.allocate_address),
    path('address/reserve/', views.reserve_address),
    path('address/release/', views.release_address),
    path('address/update/', views.update_address),
    path('address/isolate/', views.isolate_address),
    path('address/restore/', views.restore_address),
    path('security-events/', views.get_security_events),
    path('scan/start/', views.start_scan),
    path('scan/test/', views.test_connection),
    path('scan/import/', views.import_discovery),
    path('insights/', views.get_insights),
    path('change-log/', views.get_change_logs),
    path('isolation-template/', views.IsolationTemplateView.as_view()),
]
