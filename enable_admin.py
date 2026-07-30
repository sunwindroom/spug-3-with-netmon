import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=30)

# Enable admin user
cmd = 'docker exec spug python3 /data/spug/spug_api/manage.py shell -c "from apps.account.models import User; u=User.objects.get(username=\'admin\'); u.is_active=True; u.save(); print(\'User enabled:\', u.is_active)"'
stdin, stdout, stderr = client.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())

client.close()