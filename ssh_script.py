import paramiko
import sys

def run_script(script_content, timeout=300):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=10)
    stdin, stdout, stderr = client.exec_command(f'bash -s', timeout=timeout)
    stdin.write(script_content)
    stdin.flush()
    stdin.channel.shutdown_write()
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
    script = sys.argv[1]
    run_script(script)