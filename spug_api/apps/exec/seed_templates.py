# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
一批"开箱即用"的监控脚本模板定义（供 ExecTemplate 使用），
覆盖操作系统（Linux/Windows）、数据库（MySQL/MariaDB/Oracle/PostgreSQL/MongoDB/Redis）、
中间件（Nginx/Tomcat/Apache）、容器（Docker）等常见目标，参考 Zabbix/Nagios/Prometheus
生态中广泛使用的检测思路（资源阈值判断、进程存活、服务自带状态接口）编写，
统一约定："输出说明信息 + 正常退出码0 / 异常退出码非0"，可直接在
「监控中心 → 新建任务 → 自定义脚本 → 从模板添加」中选用，也可在「配置中心 → 执行模板」
中作为批量运维脚本使用。

本模块被两处调用：
  1. apps.exec.apps.ExecConfig.ready() —— 每次执行 migrate/updatedb 后自动静默补种，
     确保任何部署方式（首次安装/在线升级/Docker）都不会遗漏这批模板；
  2. management/commands/seed_script_templates.py —— 供手动重新执行并查看结果统计。
幂等：按模板名称去重，已存在同名模板则跳过，不会覆盖用户的自定义修改。
"""

TEMPLATES = [
    # ------------------------------------------------------------ Linux 操作系统 -----
    {
        'type': 'Linux-操作系统', 'name': 'Linux-CPU使用率检查', 'interpreter': 'sh',
        'desc': '检查CPU使用率是否超过阈值，可修改脚本内 THRESHOLD 调整告警线',
        'body': '''#!/bin/bash
# 检查CPU使用率是否超过阈值，超过则异常退出。可根据需要修改 THRESHOLD。
THRESHOLD=90
CPU_IDLE=$(top -bn1 | grep "Cpu(s)" | awk -F',' '{for(i=1;i<=NF;i++){if($i ~ /id/){gsub(/[^0-9.]/,"",$i);print $i}}}')
CPU_USAGE=$(awk -v idle="$CPU_IDLE" 'BEGIN{printf "%.0f", 100-idle}')
echo "当前CPU使用率: ${CPU_USAGE}%（阈值 ${THRESHOLD}%）"
if [ "$CPU_USAGE" -ge "$THRESHOLD" ]; then
  echo "CPU使用率过高"
  exit 1
fi
exit 0
'''
    },
    {
        'type': 'Linux-操作系统', 'name': 'Linux-内存使用率检查', 'interpreter': 'sh',
        'desc': '检查内存使用率是否超过阈值',
        'body': '''#!/bin/bash
THRESHOLD=90
MEM_USAGE=$(free | awk '/Mem:/ {printf "%.0f", $3/$2*100}')
echo "当前内存使用率: ${MEM_USAGE}%（阈值 ${THRESHOLD}%）"
if [ "$MEM_USAGE" -ge "$THRESHOLD" ]; then
  echo "内存使用率过高"
  exit 1
fi
exit 0
'''
    },
    {
        'type': 'Linux-操作系统', 'name': 'Linux-磁盘使用率检查', 'interpreter': 'sh',
        'desc': '检查指定挂载点磁盘使用率，默认检查根分区 /，可修改 MOUNT_POINT',
        'body': '''#!/bin/bash
THRESHOLD=85
MOUNT_POINT=/
DISK_USAGE=$(df -P "$MOUNT_POINT" | awk 'NR==2 {gsub("%","",$5); print $5}')
echo "挂载点 ${MOUNT_POINT} 磁盘使用率: ${DISK_USAGE}%（阈值 ${THRESHOLD}%）"
if [ "$DISK_USAGE" -ge "$THRESHOLD" ]; then
  echo "磁盘空间不足"
  exit 1
fi
exit 0
'''
    },
    {
        'type': 'Linux-操作系统', 'name': 'Linux-系统负载检查', 'interpreter': 'sh',
        'desc': '以CPU核数作为1分钟负载基准阈值进行判断',
        'body': '''#!/bin/bash
THRESHOLD=$(nproc)
LOAD1=$(awk '{print $1}' /proc/loadavg)
OK=$(awk -v l="$LOAD1" -v t="$THRESHOLD" 'BEGIN{print (l<t)?1:0}')
echo "当前1分钟负载: ${LOAD1}（CPU核数: ${THRESHOLD}）"
if [ "$OK" -eq 0 ]; then
  echo "系统负载过高"
  exit 1
fi
exit 0
'''
    },
    {
        'type': 'Linux-操作系统', 'name': 'Linux-僵尸进程检查', 'interpreter': 'sh',
        'desc': '统计当前僵尸进程(zombie)数量',
        'body': '''#!/bin/bash
THRESHOLD=5
ZOMBIE_COUNT=$(ps -eo stat | grep -c '^Z')
echo "当前僵尸进程数: ${ZOMBIE_COUNT}（阈值 ${THRESHOLD}）"
if [ "$ZOMBIE_COUNT" -ge "$THRESHOLD" ]; then
  echo "僵尸进程数过多，建议排查父进程"
  exit 1
fi
exit 0
'''
    },
    {
        'type': 'Linux-操作系统', 'name': 'Linux-SSH登录失败次数检查', 'interpreter': 'sh',
        'desc': '统计近1小时SSH登录失败次数，用于发现疑似暴力破解',
        'body': '''#!/bin/bash
THRESHOLD=20
LOGFILE=/var/log/secure
[ -f "$LOGFILE" ] || LOGFILE=/var/log/auth.log
COUNT=$(grep "Failed password" "$LOGFILE" 2>/dev/null | grep "$(date -d '1 hour ago' '+%b %e %H' 2>/dev/null || date '+%b %e %H')" | wc -l)
echo "近1小时SSH登录失败次数: ${COUNT}（阈值 ${THRESHOLD}）"
if [ "$COUNT" -ge "$THRESHOLD" ]; then
  echo "登录失败次数异常，疑似暴力破解，建议检查 /var/log/secure 与 fail2ban"
  exit 1
fi
exit 0
'''
    },
    # ------------------------------------------------------------ Windows 操作系统 -----
    {
        'type': 'Windows-操作系统', 'name': 'Windows-CPU使用率检查', 'interpreter': 'sh',
        'desc': 'PowerShell脚本，需目标主机安装OpenSSH Server（建议将默认Shell设置为PowerShell）',
        'body': '''# 需要目标Windows主机已安装 OpenSSH Server
# 建议将OpenSSH默认Shell设置为PowerShell：
#   New-ItemProperty -Path "HKLM:\\SOFTWARE\\OpenSSH" -Name DefaultShell `
#     -Value "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -PropertyType String -Force
$Threshold = 90
$Usage = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
Write-Output "当前CPU使用率: $Usage% (阈值 $Threshold%)"
if ($Usage -ge $Threshold) { exit 1 } else { exit 0 }
'''
    },
    {
        'type': 'Windows-操作系统', 'name': 'Windows-内存使用率检查', 'interpreter': 'sh',
        'desc': 'PowerShell脚本，检查物理内存使用率',
        'body': '''$Threshold = 90
$os = Get-CimInstance Win32_OperatingSystem
$Usage = [math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100)
Write-Output "当前内存使用率: $Usage% (阈值 $Threshold%)"
if ($Usage -ge $Threshold) { exit 1 } else { exit 0 }
'''
    },
    {
        'type': 'Windows-操作系统', 'name': 'Windows-磁盘空间检查', 'interpreter': 'sh',
        'desc': 'PowerShell脚本，默认检查C盘，可修改 $Drive',
        'body': '''$Threshold = 85
$Drive = "C:"
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$Drive'"
$Usage = [math]::Round((($disk.Size - $disk.FreeSpace) / $disk.Size) * 100)
Write-Output "磁盘 $Drive 使用率: $Usage% (阈值 $Threshold%)"
if ($Usage -ge $Threshold) { exit 1 } else { exit 0 }
'''
    },
    {
        'type': 'Windows-操作系统', 'name': 'Windows-服务状态检查', 'interpreter': 'sh',
        'desc': '检查指定Windows服务是否处于Running状态，请替换 $ServiceName',
        'body': '''$ServiceName = "Spooler"  # 请替换为需要检查的服务名称（Get-Service查看）
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($null -eq $svc) { Write-Output "服务 $ServiceName 不存在"; exit 1 }
if ($svc.Status -ne 'Running') { Write-Output "服务 $ServiceName 状态: $($svc.Status)"; exit 1 }
Write-Output "服务 $ServiceName 运行正常"
exit 0
'''
    },
    {
        'type': 'Windows-操作系统', 'name': 'Windows-IIS站点状态检查', 'interpreter': 'sh',
        'desc': '需已安装IIS管理模块(WebAdministration)，请替换 $SiteName',
        'body': '''Import-Module WebAdministration -ErrorAction SilentlyContinue
$SiteName = "Default Web Site"  # 请替换为站点名称
$site = Get-Website -Name $SiteName -ErrorAction SilentlyContinue
if ($null -eq $site) { Write-Output "站点 $SiteName 不存在"; exit 1 }
if ($site.State -ne 'Started') { Write-Output "站点 $SiteName 状态: $($site.State)"; exit 1 }
Write-Output "站点 $SiteName 运行正常"
exit 0
'''
    },
    # ------------------------------------------------------------ 容器 -----
    {
        'type': '容器-Docker', 'name': 'Docker-容器健康检查', 'interpreter': 'sh',
        'desc': '检查是否存在非running状态的容器（Exited/Restarting等）',
        'body': '''#!/bin/bash
BAD=$(docker ps -a --format '{{.Names}} {{.Status}}' | grep -v 'Up ' || true)
if [ -n "$BAD" ]; then
  echo -e "发现异常容器：\\n$BAD"
  exit 1
fi
echo "所有容器运行正常"
exit 0
'''
    },
    {
        'type': '容器-Docker', 'name': 'Docker-磁盘空间检查', 'interpreter': 'sh',
        'desc': '检查Docker数据目录磁盘使用率，超过阈值提示清理',
        'body': '''#!/bin/bash
THRESHOLD=85
DOCKER_ROOT=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)
DISK_USAGE=$(df -P "$DOCKER_ROOT" | awk 'NR==2 {gsub("%","",$5); print $5}')
echo "Docker数据目录(${DOCKER_ROOT})磁盘使用率: ${DISK_USAGE}%（阈值 ${THRESHOLD}%）"
if [ "$DISK_USAGE" -ge "$THRESHOLD" ]; then
  echo "Docker磁盘空间不足，建议执行 docker system prune 清理"
  exit 1
fi
exit 0
'''
    },
    # ------------------------------------------------------------ MySQL / MariaDB -----
    {
        'type': '数据库-MySQL_MariaDB', 'name': 'MySQL-服务存活检测', 'interpreter': 'sh',
        'desc': '使用 mysqladmin ping，适用于MySQL/MariaDB，无需权限即可判断服务是否存活',
        'body': '''#!/bin/bash
RESULT=$(mysqladmin ping 2>&1)
if echo "$RESULT" | grep -q "mysqld is alive"; then
  echo "MySQL/MariaDB服务正常"
  exit 0
else
  echo "MySQL/MariaDB服务异常: $RESULT"
  exit 1
fi
'''
    },
    {
        'type': '数据库-MySQL_MariaDB', 'name': 'MySQL-连接数检查', 'interpreter': 'sh',
        'desc': '需本机已配置 ~/.my.cnf 免密登录（建议使用只读监控账号）',
        'body': '''#!/bin/bash
THRESHOLD_PCT=80
MAX_CONN=$(mysql -N -e "SHOW VARIABLES LIKE 'max_connections';" | awk '{print $2}')
CUR_CONN=$(mysql -N -e "SHOW STATUS LIKE 'Threads_connected';" | awk '{print $2}')
if [ -z "$MAX_CONN" ] || [ -z "$CUR_CONN" ]; then
  echo "无法连接数据库，请检查 ~/.my.cnf 认证配置"
  exit 1
fi
PCT=$(awk -v c="$CUR_CONN" -v m="$MAX_CONN" 'BEGIN{printf "%.0f", c/m*100}')
echo "当前连接数: ${CUR_CONN}/${MAX_CONN}（${PCT}%，阈值 ${THRESHOLD_PCT}%）"
if [ "$PCT" -ge "$THRESHOLD_PCT" ]; then
  echo "数据库连接数接近上限"
  exit 1
fi
exit 0
'''
    },
    {
        'type': '数据库-MySQL_MariaDB', 'name': 'MySQL-主从复制延迟检查', 'interpreter': 'sh',
        'desc': '在从库执行，检查复制线程状态与延迟秒数',
        'body': '''#!/bin/bash
THRESHOLD=60
STATUS=$(mysql -N -e "SHOW SLAVE STATUS\\G" 2>/dev/null)
IO_RUNNING=$(echo "$STATUS" | grep "Slave_IO_Running:" | awk '{print $2}')
SQL_RUNNING=$(echo "$STATUS" | grep "Slave_SQL_Running:" | awk '{print $2}')
DELAY=$(echo "$STATUS" | grep "Seconds_Behind_Master:" | awk '{print $2}')
echo "IO线程: ${IO_RUNNING}，SQL线程: ${SQL_RUNNING}，延迟: ${DELAY}秒（阈值 ${THRESHOLD}秒）"
if [ "$IO_RUNNING" != "Yes" ] || [ "$SQL_RUNNING" != "Yes" ]; then
  echo "复制线程未运行"
  exit 1
fi
if [ -n "$DELAY" ] && [ "$DELAY" != "NULL" ] && [ "$DELAY" -ge "$THRESHOLD" ] 2>/dev/null; then
  echo "主从复制延迟过高"
  exit 1
fi
exit 0
'''
    },
    {
        'type': '数据库-MySQL_MariaDB', 'name': 'MariaDB-Galera集群状态检查', 'interpreter': 'sh',
        'desc': '适用于MariaDB Galera集群节点，检查节点是否处于Synced状态',
        'body': '''#!/bin/bash
STATE=$(mysql -N -e "SHOW STATUS LIKE 'wsrep_local_state_comment';" | awk '{print $2}')
CLUSTER_SIZE=$(mysql -N -e "SHOW STATUS LIKE 'wsrep_cluster_size';" | awk '{print $2}')
READY=$(mysql -N -e "SHOW STATUS LIKE 'wsrep_ready';" | awk '{print $2}')
echo "节点状态: ${STATE}，集群节点数: ${CLUSTER_SIZE}，就绪: ${READY}"
if [ "$STATE" = "Synced" ] && [ "$READY" = "ON" ]; then
  exit 0
else
  echo "Galera节点未处于Synced状态"
  exit 1
fi
'''
    },
    # ------------------------------------------------------------ Oracle -----
    {
        'type': '数据库-Oracle', 'name': 'Oracle-实例状态检查', 'interpreter': 'sh',
        'desc': '需以oracle用户执行，检查实例是否处于OPEN状态，请修改ORACLE_HOME/ORACLE_SID',
        'body': '''#!/bin/bash
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/dbhome_1  # 请按实际路径修改
export ORACLE_SID=ORCL                                       # 请按实际实例名修改
export PATH=$ORACLE_HOME/bin:$PATH
STATUS=$(echo "SELECT STATUS FROM V\\$INSTANCE;" | sqlplus -s / as sysdba 2>/dev/null | sed -n '3p' | tr -d '[:space:]')
echo "实例状态: ${STATUS}"
if [ "$STATUS" = "OPEN" ]; then
  exit 0
else
  echo "Oracle实例未处于OPEN状态"
  exit 1
fi
'''
    },
    {
        'type': '数据库-Oracle', 'name': 'Oracle-表空间使用率检查', 'interpreter': 'sh',
        'desc': '检查各表空间使用率，超过阈值列出具体表空间名称',
        'body': '''#!/bin/bash
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/dbhome_1  # 请按实际路径修改
export ORACLE_SID=ORCL                                       # 请按实际实例名修改
export PATH=$ORACLE_HOME/bin:$PATH
THRESHOLD=90
RESULT=$(sqlplus -s / as sysdba <<EOF
set heading off feedback off pagesize 0 linesize 200
SELECT tablespace_name || ':' || ROUND((1 - SUM(bytes_free)/SUM(bytes_total)) * 100)
FROM (
  SELECT tablespace_name, SUM(bytes) bytes_total, 0 bytes_free FROM dba_data_files GROUP BY tablespace_name
  UNION ALL
  SELECT tablespace_name, 0, SUM(bytes) FROM dba_free_space GROUP BY tablespace_name
)
GROUP BY tablespace_name;
EXIT;
EOF
)
echo "$RESULT"
OVER=$(echo "$RESULT" | awk -F: -v t="$THRESHOLD" '{if ($2+0 >= t) print $1}')
if [ -n "$OVER" ]; then
  echo "以下表空间使用率超过${THRESHOLD}%：$OVER"
  exit 1
fi
exit 0
'''
    },
    # ------------------------------------------------------------ Nginx -----
    {
        'type': '中间件-Nginx', 'name': 'Nginx-进程与配置检查', 'interpreter': 'sh',
        'desc': '检查进程存活并执行 nginx -t 校验配置文件语法',
        'body': '''#!/bin/bash
if ! pgrep -x nginx > /dev/null; then
  echo "Nginx进程未运行"
  exit 1
fi
OUT=$(nginx -t 2>&1)
if [ $? -ne 0 ]; then
  echo "Nginx配置文件校验失败: $OUT"
  exit 1
fi
echo "Nginx进程运行正常，配置文件校验通过"
exit 0
'''
    },
    {
        'type': '中间件-Nginx', 'name': 'Nginx-活跃连接数检查', 'interpreter': 'sh',
        'desc': '需开启 stub_status 模块：location /nginx_status { stub_status on; }',
        'body': '''#!/bin/bash
THRESHOLD=1000
STATUS_URL="http://127.0.0.1/nginx_status"
RESULT=$(curl -s --max-time 5 "$STATUS_URL")
if [ -z "$RESULT" ]; then
  echo "无法获取Nginx状态信息，请确认已开启 stub_status 模块"
  exit 1
fi
ACTIVE=$(echo "$RESULT" | awk '/Active connections/ {print $3}')
echo "当前活跃连接数: ${ACTIVE}（阈值 ${THRESHOLD}）"
if [ "$ACTIVE" -ge "$THRESHOLD" ]; then
  echo "Nginx活跃连接数过高"
  exit 1
fi
exit 0
'''
    },
    # ------------------------------------------------------------ Tomcat -----
    {
        'type': '中间件-Tomcat', 'name': 'Tomcat-进程检查', 'interpreter': 'sh',
        'desc': '检查Tomcat启动进程是否存在',
        'body': '''#!/bin/bash
if ! pgrep -f "org.apache.catalina.startup.Bootstrap" > /dev/null; then
  echo "Tomcat进程未运行"
  exit 1
fi
echo "Tomcat进程运行正常"
exit 0
'''
    },
    {
        'type': '中间件-Tomcat', 'name': 'Tomcat-JVM老年代内存使用率检查', 'interpreter': 'sh',
        'desc': '需JDK自带jstat工具，执行用户需与Tomcat进程属主一致',
        'body': '''#!/bin/bash
THRESHOLD=85
PID=$(pgrep -f "org.apache.catalina.startup.Bootstrap" | head -1)
if [ -z "$PID" ]; then
  echo "未找到Tomcat进程"
  exit 1
fi
USAGE=$(jstat -gcutil "$PID" 2>/dev/null | awk 'NR==2 {print $3}')
if [ -z "$USAGE" ]; then
  echo "无法获取JVM内存信息，请确认已安装jstat且执行用户与Tomcat一致"
  exit 1
fi
USAGE_INT=$(printf "%.0f" "$USAGE")
echo "老年代(Old区)使用率: ${USAGE_INT}%（阈值 ${THRESHOLD}%）"
if [ "$USAGE_INT" -ge "$THRESHOLD" ]; then
  echo "JVM老年代内存使用率过高，注意GC情况"
  exit 1
fi
exit 0
'''
    },
    # ------------------------------------------------------------ Apache -----
    {
        'type': '中间件-Apache', 'name': 'Apache-进程检查', 'interpreter': 'sh',
        'desc': '兼容httpd(CentOS/RHEL)与apache2(Debian/Ubuntu)进程名',
        'body': '''#!/bin/bash
if pgrep -x httpd > /dev/null || pgrep -x apache2 > /dev/null; then
  echo "Apache进程运行正常"
  exit 0
else
  echo "Apache进程未运行"
  exit 1
fi
'''
    },
    {
        'type': '中间件-Apache', 'name': 'Apache-忙碌进程数检查', 'interpreter': 'sh',
        'desc': '需开启 mod_status 模块：/server-status?auto',
        'body': '''#!/bin/bash
THRESHOLD=200
STATUS_URL="http://127.0.0.1/server-status?auto"
RESULT=$(curl -s --max-time 5 "$STATUS_URL")
if [ -z "$RESULT" ]; then
  echo "无法获取Apache状态信息，请确认已开启 mod_status 模块"
  exit 1
fi
BUSY=$(echo "$RESULT" | awk -F: '/BusyWorkers/ {gsub(" ","",$2); print $2}')
echo "当前忙碌进程数: ${BUSY}（阈值 ${THRESHOLD}）"
if [ "$BUSY" -ge "$THRESHOLD" ]; then
  echo "Apache忙碌进程数过高"
  exit 1
fi
exit 0
'''
    },
    # ------------------------------------------------------------ 其他常见组件 -----
    {
        'type': '数据库-Redis', 'name': 'Redis-连接与内存检查', 'interpreter': 'sh',
        'desc': '检查Redis服务响应与已用内存，超过阈值告警',
        'body': '''#!/bin/bash
THRESHOLD_MEM_MB=1024
PONG=$(redis-cli ping 2>/dev/null)
if [ "$PONG" != "PONG" ]; then
  echo "Redis服务无响应"
  exit 1
fi
USED_BYTES=$(redis-cli info memory 2>/dev/null | grep "^used_memory:" | cut -d: -f2 | tr -d '\\r')
USED_MB=$((USED_BYTES / 1024 / 1024))
echo "Redis已用内存: ${USED_MB}MB（阈值 ${THRESHOLD_MEM_MB}MB）"
if [ "$USED_MB" -ge "$THRESHOLD_MEM_MB" ]; then
  echo "Redis内存使用超过阈值"
  exit 1
fi
exit 0
'''
    },
    {
        'type': '数据库-PostgreSQL', 'name': 'PostgreSQL-连接数检查', 'interpreter': 'sh',
        'desc': '需本机可免密执行psql（配置.pgpass或peer认证）',
        'body': '''#!/bin/bash
THRESHOLD_PCT=80
MAX_CONN=$(psql -U postgres -tAc "SHOW max_connections;" 2>/dev/null)
CUR_CONN=$(psql -U postgres -tAc "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null)
if [ -z "$MAX_CONN" ] || [ -z "$CUR_CONN" ]; then
  echo "无法连接PostgreSQL，请检查psql客户端与认证配置"
  exit 1
fi
PCT=$(awk -v c="$CUR_CONN" -v m="$MAX_CONN" 'BEGIN{printf "%.0f", c/m*100}')
echo "当前连接数: ${CUR_CONN}/${MAX_CONN}（${PCT}%，阈值 ${THRESHOLD_PCT}%）"
if [ "$PCT" -ge "$THRESHOLD_PCT" ]; then
  echo "PostgreSQL连接数接近上限"
  exit 1
fi
exit 0
'''
    },
    {
        'type': '数据库-MongoDB', 'name': 'MongoDB-服务存活检测', 'interpreter': 'sh',
        'desc': '兼容新版mongosh与旧版mongo客户端',
        'body': '''#!/bin/bash
RESULT=$(mongosh --quiet --eval "db.adminCommand('ping').ok" 2>/dev/null || mongo --quiet --eval "db.adminCommand('ping').ok" 2>/dev/null)
if [ "$RESULT" = "1" ]; then
  echo "MongoDB服务正常"
  exit 0
else
  echo "MongoDB服务无响应"
  exit 1
fi
'''
    },
]



def seed_templates():
    """返回 (created, skipped)。找不到任何用户时返回 (0, 0) 并静默跳过（例如首次 migrate 时账号尚未创建）。"""
    import json
    from apps.account.models import User
    from apps.exec.models import ExecTemplate
    try:
        from apps.exec.management.commands.monitor_templates_data import MONITOR_TEMPLATES
    except ImportError:
        MONITOR_TEMPLATES = []

    operator = User.objects.filter(is_supper=True).first() or User.objects.first()
    if not operator:
        return 0, 0

    all_templates = list(TEMPLATES)
    seen_names = {t['name'] for t in all_templates}
    for tpl in MONITOR_TEMPLATES:
        if tpl['name'] not in seen_names:
            all_templates.append(tpl)
            seen_names.add(tpl['name'])

    created, skipped = 0, 0
    for tpl in all_templates:
        if ExecTemplate.objects.filter(name=tpl['name']).exists():
            skipped += 1
            continue
        params = tpl.get('parameters', [])
        ExecTemplate.objects.create(
            name=tpl['name'], type=tpl['type'], body=tpl['body'].strip() + '\n',
            interpreter=tpl['interpreter'], desc=tpl['desc'],
            parameters=json.dumps(params) if params else '[]',
            created_by=operator
        )
        created += 1
    return created, skipped
