import paramiko
import os
import sys

HOST = '192.168.10.203'
USER = 'root'
PASS = 'Clbr@2024'

def upload_dir(local_dir, remote_dir):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    sftp = client.open_sftp()
    
    skip_dirs = {'.git', 'node_modules', '__pycache__', '.codeartsdoer', '.arts', 'build', 'repos', 'storage', 'migrations'}
    skip_exts = {'.pyc', '.log', '.sqlite3', '.db'}
    
    count = 0
    for root, dirs, files in os.walk(local_dir):
        rel = os.path.relpath(root, local_dir)
        if rel == '.':
            remote_root = remote_dir
        else:
            parts = rel.split(os.sep)
            if any(p in skip_dirs for p in parts):
                continue
            remote_root = remote_dir + '/' + rel.replace(os.sep, '/')
        
        try:
            sftp.stat(remote_root)
        except FileNotFoundError:
            sftp.mkdir(remote_root)
        
        for f in files:
            if any(f.endswith(e) for e in skip_exts):
                continue
            local_path = os.path.join(root, f)
            remote_path = remote_root + '/' + f
            try:
                sftp.put(local_path, remote_path)
                count += 1
                if count % 50 == 0:
                    print(f'  已上传 {count} 个文件...')
            except Exception as e:
                print(f'  跳过 {local_path}: {e}')
    
    sftp.close()
    client.close()
    return count

if __name__ == '__main__':
    local = sys.argv[1]
    remote = sys.argv[2]
    print(f'上传 {local} -> {remote} ...')
    n = upload_dir(local, remote)
    print(f'完成，共上传 {n} 个文件')