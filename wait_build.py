import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=30)

# Start build in background
transport = client.get_transport()
channel = transport.open_session()
channel.exec_command('cd /opt/spug-build/docker && docker build --no-cache -t spug-netmon:latest . > /tmp/docker-build4.log 2>&1 &\n')
time.sleep(3)
print('Build started, waiting...')

for i in range(60):
    time.sleep(30)
    stdin, stdout, stderr = client.exec_command('tail -2 /tmp/docker-build4.log 2>/dev/null')
    out = stdout.read().decode().strip()
    stdin2, stdout2, stderr2 = client.exec_command('pgrep -f "docker build" | head -1')
    running = stdout2.read().decode().strip()
    status = 'RUNNING' if running else 'FINISHED'
    print(f'[{(i+1)*30}s] {status} | {out[-80:] if out else "no output"}')
    if not running and i > 3:
        break

# Final check
stdin, stdout, stderr = client.exec_command('docker images spug-netmon')
print('\n=== Docker images ===')
print(stdout.read().decode())

stdin, stdout, stderr = client.exec_command('tail -5 /tmp/docker-build4.log')
print('=== Build log tail ===')
print(stdout.read().decode())

client.close()
