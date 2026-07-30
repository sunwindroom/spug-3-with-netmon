import paramiko
import sys
import time

def exec_long_cmd(cmd, timeout=600):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=10)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    client.close()
    if out:
        print(out, end='')
    if err:
        print(err, end='', file=sys.stderr)
    return code

if __name__ == '__main__':
    cmd = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else 'echo hello'
    timeout = int(sys.argv[1]) if len(sys.argv) > 2 and sys.argv[1].isdigit() else 600
    sys.exit(exec_long_cmd(cmd, timeout))