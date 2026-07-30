import paramiko
import time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=30)

# Start build in background using transport
transport = client.get_transport()
channel = transport.open_session()
channel.exec_command('cd /opt/spug-build/docker && docker build --no-cache -t spug-netmon:latest . > /tmp/docker-build.log 2>&1 &\necho BUILD_STARTED\n')
time.sleep(5)

# Check build progress
stdin, stdout, stderr = client.exec_command('tail -5 /tmp/docker-build.log 2>/dev/null || echo Waiting for build log...')
out = stdout.read().decode()
print(f'Build log: {out}')

# Check if docker build process is running
stdin, stdout, stderr = client.exec_command('pgrep -f "docker build" && echo BUILD_RUNNING || echo BUILD_NOT_RUNNING')
out = stdout.read().decode()
print(f'Status: {out}')

client.close()