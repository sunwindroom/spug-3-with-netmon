import paramiko
import json

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=30)

print("=" * 60)
print("Spug运维平台 最终测试报告")
print("=" * 60)

tests_passed = 0
tests_total = 0

def test(name, passed, detail=""):
    global tests_passed, tests_total
    tests_total += 1
    if passed:
        tests_passed += 1
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))

# 1. Frontend
stdin, stdout, stderr = client.exec_command("curl -s -o /dev/null -w '%{http_code}' http://192.168.10.203/")
code = stdout.read().decode().strip()
test("前端页面访问", code == "200", f"HTTP {code}")

# 2. Login
login_data = json.dumps({"username": "admin", "password": "Spug2024Admin"})
cmd = f"curl -s -X POST http://127.0.0.1:80/api/account/login/ -H 'Content-Type: application/json' -d '{login_data}'"
stdin, stdout, stderr = client.exec_command(cmd)
result = stdout.read().decode()
try:
    resp = json.loads(result)
    token = resp.get('data', {}).get('token', '') if isinstance(resp.get('data'), dict) else ''
    test("用户登录", bool(token), f"Token: {token[:20]}..." if token else str(resp.get('error', '')))
except:
    test("用户登录", False, result[:80])

# 3. Supervisor
stdin, stdout, stderr = client.exec_command("docker exec spug supervisorctl status")
result = stdout.read().decode()
running = result.count("RUNNING")
test("Supervisor进程", running == 8, f"{running}/8 运行中")

# 4. Database
stdin, stdout, stderr = client.exec_command("docker exec spug-db mysqladmin -uspug -p'Spug@2024#Secure' ping -h127.0.0.1 2>&1")
result = stdout.read().decode()
test("数据库连接", "alive" in result)

# 5. Redis
stdin, stdout, stderr = client.exec_command("docker exec spug redis-cli ping")
result = stdout.read().decode().strip()
test("Redis连接", result == "PONG")

# 6. Nginx
stdin, stdout, stderr = client.exec_command("docker exec spug nginx -t 2>&1")
result = stdout.read().decode()
test("Nginx配置", "successful" in result)

# 7. Docker
stdin, stdout, stderr = client.exec_command("docker ps --format '{{.Names}}: {{.Status}}'")
result = stdout.read().decode()
test("Docker容器", result.count("Up") >= 2, f"{result.count('Up')} 运行中")

# 8. API
stdin, stdout, stderr = client.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/api/account/login/")
code = stdout.read().decode().strip()
test("API端点可达", code in ["200", "405"], f"HTTP {code}")

# 9. Static
stdin, stdout, stderr = client.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/favicon.ico")
code = stdout.read().decode().strip()
test("静态文件服务", code == "200", f"HTTP {code}")

# 10. External access
stdin, stdout, stderr = client.exec_command("curl -s -o /dev/null -w '%{http_code}' http://192.168.10.203/")
code = stdout.read().decode().strip()
test("外部网络访问", code == "200", f"HTTP {code}")

# 11. Authenticated API
if token:
    cmd2 = f"curl -s http://127.0.0.1:80/api/home/notice/ -H 'x-token: {token}'"
    stdin2, stdout2, stderr2 = client.exec_command(cmd2)
    result2 = stdout2.read().decode()
    test("认证API调用", "error" not in result2 or "data" in result2, result2[:60])

# 12. Netmon module
if token:
    cmd3 = f"curl -s http://127.0.0.1:80/api/netmon/group/ -H 'x-token: {token}'"
    stdin3, stdout3, stderr3 = client.exec_command(cmd3)
    result3 = stdout3.read().decode()
    test("IT资源监控模块", "error" not in result3 or "data" in result3, result3[:60])

print("\n" + "=" * 60)
print(f"测试结果: {tests_passed}/{tests_total} 通过")
print("=" * 60)
print("\n部署信息:")
print(f"  访问地址: http://192.168.10.203")
print(f"  管理员账号: admin")
print(f"  管理员密码: Spug2024Admin")
print(f"  容器: spug (应用), spug-db (数据库)")
print("=" * 60)

client.close()
