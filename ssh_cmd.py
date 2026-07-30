import paramiko
import sys
import os

HOST = '192.168.10.203'
USER = 'root'
PASS = 'Clbr@2024'

def ssh_exec(cmd, timeout=300):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    client.close()
    return out, err, code

def upload_file(local_path, remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()

if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'exec':
        cmd = ' '.join(sys.argv[2:])
        out, err, code = ssh_exec(cmd)
        if out: print(out, end='')
        if err: print(err, end='', file=sys.stderr)
        sys.exit(code)
    elif action == 'upload':
        upload_file(sys.argv[2], sys.argv[3])
        print(f'Uploaded {sys.argv[2]} -> {sys.argv[3]}')
