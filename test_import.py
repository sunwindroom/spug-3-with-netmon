import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spug.settings')
import django
django.setup()
from django.test import RequestFactory
from apps.account.models import User
from apps.ipam.views import import_discovery

user = User.objects.get(pk=1)
factory = RequestFactory()
req = factory.post('/api/ipam/scan/import/', 
    data='{"subnet_id": 1, "devices": []}',
    content_type='application/json')
req.user = user
print(f'request.user = {req.user}, id = {req.user.id}')
result = import_discovery(req)
print(f'result = {result}')