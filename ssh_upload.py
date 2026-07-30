import paramiko
import sys
import os

def upload_file(local_path, remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=10)
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()
    print(f"Uploaded: {local_path} -> {remote_path}")

if __name__ == '__main__':
    local = sys.argv[1]
    remote = sys.argv[2]
    upload_file(local, remote)