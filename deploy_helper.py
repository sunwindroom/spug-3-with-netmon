import paramiko
import sys

def run_ssh_command(host, username, password, command):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username, password=password, timeout=10)
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        client.close()
        return output, error
    except Exception as e:
        return '', str(e)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python deploy_helper.py <command>")
        sys.exit(1)
    
    host = '192.168.10.203'
    username = 'root'
    password = 'Clbr@2024'
    command = sys.argv[1]
    
    output, error = run_ssh_command(host, username, password, command)
    if output:
        print(output, end='')
    if error:
        print(error, end='', file=sys.stderr)