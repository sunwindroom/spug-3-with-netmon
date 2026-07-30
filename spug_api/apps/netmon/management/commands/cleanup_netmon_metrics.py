from django.core.management.base import BaseCommand
from django.conf import settings
from apps.netmon.models import MetricRecord, AnomalyEvent
from datetime import timedelta
from django.utils import timezone
import logging


class Command(BaseCommand):
    help = 'Cleanup old netmon metric records and resolved anomaly events to prevent database bloat'

    def add_arguments(self, parser):
        parser.add_argument('--metric-days', type=int, default=30, help='Retain metric records for N days (default 30)')
        parser.add_argument('--anomaly-days', type=int, default=90, help='Retain resolved anomaly events for N days (default 90)')

    def handle(self, *args, **options):
        metric_days = options['metric_days']
        anomaly_days = options['anomaly_days']

        metric_cutoff = timezone.now() - timedelta(days=metric_days)
        metric_count, _ = MetricRecord.objects.filter(collected_at__lt=metric_cutoff).delete()
        logging.warning(f'Cleaned up {metric_count} metric records older than {metric_days} days')

        anomaly_cutoff = (timezone.now() - timedelta(days=anomaly_days)).strftime('%Y-%m-%d %H:%M:%S')
        anomaly_count, _ = AnomalyEvent.objects.filter(
            status='resolved', resolved_at__lt=anomaly_cutoff
        ).delete()
        logging.warning(f'Cleaned up {anomaly_count} resolved anomaly events older than {anomaly_days} days')

        self.stdout.write(self.style.SUCCESS(
            f'Cleanup complete: {metric_count} metrics (>{metric_days}d), {anomaly_count} anomalies (>{anomaly_days}d)'
        ))