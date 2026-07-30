import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=30)

cmd = """docker exec spug python3 /data/spug/spug_api/manage.py shell -c "
from apps.exec.models import ExecTemplate
print('模板总数:', ExecTemplate.objects.count())
for t in [x['type'] for x in ExecTemplate.objects.order_by('type').values('type').distinct()]:
    count = ExecTemplate.objects.filter(type=t).count()
    print(f'  [{t}]: {count}个模板')
" """
stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode())
client.close()