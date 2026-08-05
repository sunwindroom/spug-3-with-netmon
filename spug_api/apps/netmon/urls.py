# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.urls import path
from apps.netmon import views

urlpatterns = [

    path('device/', views.DeviceView.as_view()),
    path('device/batch-delete/', views.batch_delete_devices),
    path('device/import-csv/', views.import_devices_csv),
    path('device/test-connectivity/', views.test_connectivity),
    path('topology/', views.TopologyView.as_view()),
    path('overview/', views.get_overview),
    path('metric/history/', views.get_metric_history),
    path('anomaly/', views.AnomalyView.as_view()),
    path('alert-rule/', views.AlertRuleView.as_view()),
    path('maintenance-window/', views.MaintenanceWindowView.as_view()),
    path('remediation-action/', views.RemediationActionView.as_view()),
    path('remediation-log/', views.get_remediation_logs),
    path('discovery/start/', views.start_discovery),
    path('discovery/result/', views.get_discovery_result),
    path('discovery/import/', views.import_discovery),
    path('report/', views.ReportView.as_view()),
    path('report/generate/', views.generate_report),
    path('report/record/', views.get_report_records),
    path('report/download/', views.download_report),
]
