import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.10.203', username='root', password='Clbr@2024', timeout=30)

tests = [
    # Test 1: Frontend page
    ("前端页面访问", "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/"),
    
    # Test 2: Login API
    ("登录API", "curl -s -X POST http://127.0.0.1:80/api/account/login/ -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"Spug@2024\"}'"),
    
    # Test 3: Basic settings API
    ("基础设置API", "curl -s http://127.0.0.1:80/api/setting/basic/"),
    
    # Test 4: Container status
    ("容器状态", "docker ps --format '{{.Names}}: {{.Status}}'"),
    
    # Test 5: Supervisor status
    ("Supervisor进程", "docker exec spug supervisorctl status"),
    
    # Test 6: DB connection
    ("数据库连接", "docker exec spug-db mysqladmin -uspug -p'Spug@2024#Secure' ping -h127.0.0.1 2>&1"),
    
    # Test 7: Redis connection
    ("Redis连接", "docker exec spug redis-cli ping"),
    
    # Test 8: Nginx status
    ("Nginx状态", "docker exec spug nginx -t 2>&1"),
]

print("=" * 60)
print("Spug运维平台 部署测试报告")
print("=" * 60)

passed = 0
failed = 0

for name, cmd in tests:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    result = out if out else err
    
    if name == "前端页面访问":
        status = "PASS" if result == "200" else "FAIL"
    elif name == "登录API":
        status = "PASS" if "token" in result.lower() or "data" in result.lower() else "FAIL"
    elif name == "数据库连接":
        status = "PASS" if "alive" in result.lower() or "mysqld is alive" in result.lower() else "FAIL"
    elif name == "Redis连接":
        status = "PASS" if "PONG" in result else "FAIL"
    elif name == "Nginx状态":
        status = "PASS" if "successful" in result else "FAIL"
    elif name == "Supervisor进程":
        status = "PASS" if "RUNNING" in result else "FAIL"
    elif name == "容器状态":
        status = "PASS" if "Up" in result else "FAIL"
    else:
        status = "INFO"
    
    if status == "PASS":
        passed += 1
    elif status == "FAIL":
        failed += 1
    
    print(f"\n[{status}] {name}")
    if len(result) < 200:
        print(f"  结果: {result}")
    else:
        print(f"  结果: {result[:200]}...")

print("\n" + "=" * 60)
print(f"测试结果: {passed} 通过, {failed} 失败")
print("=" * 60)

client.close()