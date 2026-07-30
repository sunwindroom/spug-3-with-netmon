import paramiko
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=30)

# Test login
login_data = json.dumps({"username": "admin", "password": "Spug@2024"})
cmd = f"curl -s -X POST http://127.0.0.1:80/api/account/login/ -H 'Content-Type: application/json' -d '{login_data}'"
stdin, stdout, stderr = client.exec_command(cmd)
result = stdout.read().decode()
print(f"登录测试: {result}")

if '"token"' in result or '"data"' in result:
    try:
        resp = json.loads(result)
        if resp.get('data') and isinstance(resp['data'], dict) and 'token' in resp['data']:
            token = resp['data']['token']
            print(f"登录成功! Token: {token[:20]}...")
            
            # Test authenticated API
            cmd2 = f"curl -s http://127.0.0.1:80/api/home/notice/ -H 'x-token: {token}'"
            stdin2, stdout2, stderr2 = client.exec_command(cmd2)
            result2 = stdout2.read().decode()
            print(f"认证API测试: {result2[:100]}")
        else:
            print(f"登录响应: {result}")
    except:
        print(f"登录响应: {result}")

# Test external access
cmd3 = "curl -s -o /dev/null -w '%{http_code}' http://192.168.10.203:80/"
stdin3, stdout3, stderr3 = client.exec_command(cmd3)
result3 = stdout3.read().decode()
print(f"\n外部访问测试 (http://192.168.10.203:80/): HTTP {result3}")

# Test all supervisor processes
cmd4 = "docker exec spug supervisorctl status"
stdin4, stdout4, stderr4 = client.exec_command(cmd4)
result4 = stdout4.read().decode()
running_count = result4.count("RUNNING")
total_count = len(result4.strip().split('\n'))
print(f"\n进程状态: {running_count}/{total_count} 运行中")
print(result4)

client.close()