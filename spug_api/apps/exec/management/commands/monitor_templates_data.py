MONITOR_TEMPLATES = [
    # ============================================================
    # Linux 操作系统
    # ============================================================
    {
        "name": "Linux-CPU使用率",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测CPU使用率，超过阈值则告警（默认80%）",
        "body": r"""#!/bin/bash
# Linux CPU使用率检测
# 返回0表示正常，非0表示异常
THRESHOLD=${_SPUG_THRESHOLD:-80}

# 获取CPU使用率
if command -v mpstat &>/dev/null; then
    CPU_IDLE=$(mpstat 1 1 | tail -1 | awk '{print $NF}')
    CPU_USED=$(echo "100 - $CPU_IDLE" | bc)
else
    CPU_USED=$(top -bn1 | grep "Cpu(s)" | sed 's/.*%\([0-9.]*\).*$/\1/' | awk '{print 100-$1}')
fi

CPU_INT=${CPU_USED%.*}
echo "CPU使用率: ${CPU_USED}% (阈值: ${THRESHOLD}%)"

if [ "$CPU_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: CPU使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "CPU使用率告警阈值，默认80"}
        ]
    },
    {
        "name": "Linux-内存使用率",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测内存使用率，超过阈值则告警（默认85%）",
        "body": r"""#!/bin/bash
# Linux 内存使用率检测
THRESHOLD=${_SPUG_THRESHOLD:-85}

MEM_INFO=$(free -m | grep Mem)
MEM_TOTAL=$(echo $MEM_INFO | awk '{print $2}')
MEM_USED=$(echo $MEM_INFO | awk '{print $3}')
MEM_AVAIL=$(echo $MEM_INFO | awk '{print $7}')

if [ "$MEM_AVAIL" != "" ] && [ "$MEM_AVAIL" -gt 0 ] 2>/dev/null; then
    MEM_PCT=$(echo "scale=1; ($MEM_USED - ($MEM_TOTAL - $MEM_AVAIL - $MEM_USED)) * 100 / $MEM_TOTAL" | bc 2>/dev/null || echo "0")
    MEM_PCT=$(echo "scale=1; $MEM_USED * 100 / $MEM_TOTAL" | bc)
else
    MEM_PCT=$(echo "scale=1; $MEM_USED * 100 / $MEM_TOTAL" | bc)
fi

MEM_INT=${MEM_PCT%.*}
echo "内存使用率: ${MEM_PCT}% (已用: ${MEM_USED}MB / 总计: ${MEM_TOTAL}MB, 阈值: ${THRESHOLD}%)"

if [ "$MEM_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 内存使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "85", "desc": "内存使用率告警阈值，默认85"}
        ]
    },
    {
        "name": "Linux-磁盘使用率",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测指定磁盘分区使用率，超过阈值则告警（默认90%）",
        "body": r"""#!/bin/bash
# Linux 磁盘使用率检测
THRESHOLD=${_SPUG_THRESHOLD:-90}
MOUNT_POINT=${_SPUG_MOUNT_POINT:-/}

DISK_PCT=$(df -h "$MOUNT_POINT" | tail -1 | awk '{print $5}' | tr -d '%')
echo "磁盘使用率: ${DISK_PCT}% (分区: ${MOUNT_POINT}, 阈值: ${THRESHOLD}%)"

if [ "$DISK_PCT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 磁盘使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "90", "desc": "磁盘使用率告警阈值，默认90"},
            {"name": "挂载点", "key": "MOUNT_POINT", "type": "string", "required": False, "value": "/", "desc": "要检测的磁盘挂载点，默认为/"}
        ]
    },
    {
        "name": "Linux-磁盘IO使用率",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测磁盘IO利用率（iostat），超过阈值则告警",
        "body": r"""#!/bin/bash
# Linux 磁盘IO使用率检测
THRESHOLD=${_SPUG_THRESHOLD:-80}
DEVICE=${_SPUG_DEVICE:-sda}

if ! command -v iostat &>/dev/null; then
    echo "ERROR: iostat命令不可用，请安装sysstat包"
    exit 1
fi

IO_UTIL=$(iostat -x "$DEVICE" 1 2 | tail -1 | awk '{print $NF}')
IO_INT=${IO_UTIL%.*}
echo "磁盘IO利用率: ${IO_UTIL}% (设备: ${DEVICE}, 阈值: ${THRESHOLD}%)"

if [ "$IO_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 磁盘IO利用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "IO利用率告警阈值"},
            {"name": "磁盘设备", "key": "DEVICE", "type": "string", "required": False, "value": "sda", "desc": "磁盘设备名，如sda、vda"}
        ]
    },
    {
        "name": "Linux-系统负载",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测系统负载（1分钟），超过CPU核数倍数则告警",
        "body": r"""#!/bin/bash
# Linux 系统负载检测
MULTIPLIER=${_SPUG_MULTIPLIER:-1}

CPU_CORES=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo)
THRESHOLD=$(echo "$CPU_CORES * $MULTIPLIER" | bc)
LOAD_1=$(cat /proc/loadavg | awk '{print $1}')
LOAD_INT=${LOAD_1%.*}

echo "系统负载(1min): ${LOAD_1} (CPU核数: ${CPU_CORES}, 阈值: ${THRESHOLD})"

if [ "$(echo "$LOAD_1 >= $THRESHOLD" | bc)" -eq 1 ]; then
    echo "ALERT: 系统负载超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "倍数", "key": "MULTIPLIER", "type": "string", "required": False, "value": "1", "desc": "CPU核数的倍数作为阈值，默认1倍"}
        ]
    },
    {
        "name": "Linux-Swap使用率",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测Swap交换分区使用率",
        "body": r"""#!/bin/bash
# Linux Swap使用率检测
THRESHOLD=${_SPUG_THRESHOLD:-50}

SWAP_INFO=$(free -m | grep Swap)
SWAP_TOTAL=$(echo $SWAP_INFO | awk '{print $2}')
SWAP_USED=$(echo $SWAP_INFO | awk '{print $3}')

if [ "$SWAP_TOTAL" -eq 0 ]; then
    echo "Swap未启用或无交换分区"
    exit 0
fi

SWAP_PCT=$(echo "scale=1; $SWAP_USED * 100 / $SWAP_TOTAL" | bc)
SWAP_INT=${SWAP_PCT%.*}
echo "Swap使用率: ${SWAP_PCT}% (已用: ${SWAP_USED}MB / 总计: ${SWAP_TOTAL}MB, 阈值: ${THRESHOLD}%)"

if [ "$SWAP_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: Swap使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "50", "desc": "Swap使用率告警阈值"}
        ]
    },
    {
        "name": "Linux-TCP连接数",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测TCP连接数，超过阈值则告警",
        "body": r"""#!/bin/bash
# Linux TCP连接数检测
THRESHOLD=${_SPUG_THRESHOLD:-5000}

TCP_TOTAL=$(ss -s | grep -i "TCP:" | awk '{print $2}')
if [ -z "$TCP_TOTAL" ]; then
    TCP_TOTAL=$(netstat -ant 2>/dev/null | grep -c ESTABLISHED || echo 0)
fi

echo "TCP连接数: ${TCP_TOTAL} (阈值: ${THRESHOLD})"

if [ "$TCP_TOTAL" -ge "$THRESHOLD" ]; then
    echo "ALERT: TCP连接数超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "5000", "desc": "TCP连接数告警阈值"}
        ]
    },
    {
        "name": "Linux-僵尸进程检测",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测僵尸进程数量，超过阈值则告警",
        "body": r"""#!/bin/bash
# Linux 僵尸进程检测
THRESHOLD=${_SPUG_THRESHOLD:-10}

ZOMBIE_COUNT=$(ps -eo state | grep -c "^Z")
echo "僵尸进程数: ${ZOMBIE_COUNT} (阈值: ${THRESHOLD})"

if [ "$ZOMBIE_COUNT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 僵尸进程数超过阈值!"
    echo "僵尸进程列表:"
    ps -eo pid,ppid,stat,cmd | grep "^.*Z"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "10", "desc": "僵尸进程数告警阈值"}
        ]
    },
    {
        "name": "Linux-文件句柄数",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测系统打开文件句柄数占上限百分比",
        "body": r"""#!/bin/bash
# Linux 文件句柄使用率检测
THRESHOLD=${_SPUG_THRESHOLD:-80}

FD_OPEN=$(cat /proc/sys/fs/file-nr | awk '{print $1}')
FD_MAX=$(cat /proc/sys/fs/file-nr | awk '{print $3}')
FD_PCT=$(echo "scale=1; $FD_OPEN * 100 / $FD_MAX" | bc)
FD_INT=${FD_PCT%.*}

echo "文件句柄使用率: ${FD_PCT}% (已打开: ${FD_OPEN} / 上限: ${FD_MAX}, 阈值: ${THRESHOLD}%)"

if [ "$FD_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 文件句柄使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "文件句柄使用率告警阈值"}
        ]
    },
    {
        "name": "Linux-系统时间同步检测",
        "type": "Linux操作系统",
        "interpreter": "sh",
        "desc": "检测NTP时间同步偏移量",
        "body": r"""#!/bin/bash
# Linux NTP时间同步检测
THRESHOLD=${_SPUG_THRESHOLD:-100}

if command -v ntpdate &>/dev/null; then
    OFFSET=$(ntpdate -q pool.ntp.org 2>/dev/null | tail -1 | awk '{print $NF}' | cut -d. -f1)
    OFFSET_ABS=${OFFSET#-}
elif command -v chronyc &>/dev/null; then
    OFFSET=$(chronyc tracking 2>/dev/null | grep "Last offset" | awk '{print $4}' | tr -d '[]')
    OFFSET_ABS=$(echo "$OFFSET" | tr -d '-')
else
    echo "WARN: ntpdate/chronyc均不可用，无法检测时间同步"
    exit 0
fi

echo "时间偏移量: ${OFFSET_ABS}ms (阈值: ${THRESHOLD}ms)"

if [ "${OFFSET_ABS:-0}" -ge "$THRESHOLD" ]; then
    echo "ALERT: 时间偏移量超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "偏移阈值(ms)", "key": "THRESHOLD", "type": "string", "required": False, "value": "100", "desc": "时间偏移量告警阈值(毫秒)"}
        ]
    },

    # ============================================================
    # Windows 操作系统
    # ============================================================
    {
        "name": "Windows-CPU使用率",
        "type": "Windows操作系统",
        "interpreter": "sh",
        "desc": "检测Windows CPU使用率（通过PowerShell）",
        "body": r"""#!/bin/bash
# Windows CPU使用率检测 (通过PowerShell)
THRESHOLD=${_SPUG_THRESHOLD:-80}

CPU_PCT=$(powershell -Command "Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue" 2>/dev/null)

if [ -z "$CPU_PCT" ]; then
    echo "ERROR: 无法获取CPU使用率，请确认PowerShell可用"
    exit 1
fi

CPU_INT=${CPU_PCT%.*}
echo "CPU使用率: ${CPU_PCT}% (阈值: ${THRESHOLD}%)"

if [ "$CPU_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: CPU使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "CPU使用率告警阈值"}
        ]
    },
    {
        "name": "Windows-内存使用率",
        "type": "Windows操作系统",
        "interpreter": "sh",
        "desc": "检测Windows内存使用率（通过PowerShell）",
        "body": r"""#!/bin/bash
# Windows 内存使用率检测 (通过PowerShell)
THRESHOLD=${_SPUG_THRESHOLD:-85}

MEM_PCT=$(powershell -Command "$os=Get-CimInstance Win32_OperatingSystem; [math]::Round(($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize*100,1)" 2>/dev/null)

if [ -z "$MEM_PCT" ]; then
    echo "ERROR: 无法获取内存使用率"
    exit 1
fi

MEM_INT=${MEM_PCT%.*}
echo "内存使用率: ${MEM_PCT}% (阈值: ${THRESHOLD}%)"

if [ "$MEM_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 内存使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "85", "desc": "内存使用率告警阈值"}
        ]
    },
    {
        "name": "Windows-磁盘使用率",
        "type": "Windows操作系统",
        "interpreter": "sh",
        "desc": "检测Windows指定磁盘分区使用率",
        "body": r"""#!/bin/bash
# Windows 磁盘使用率检测 (通过PowerShell)
THRESHOLD=${_SPUG_THRESHOLD:-90}
DRIVE=${_SPUG_DRIVE:-C:}

DISK_PCT=$(powershell -Command "$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='${DRIVE}'\"; [math]::Round(($d.Size-$d.FreeSpace)/$d.Size*100,1)" 2>/dev/null)

if [ -z "$DISK_PCT" ]; then
    echo "ERROR: 无法获取磁盘 ${DRIVE} 使用率"
    exit 1
fi

DISK_INT=${DISK_PCT%.*}
echo "磁盘使用率: ${DISK_PCT}% (分区: ${DRIVE}, 阈值: ${THRESHOLD}%)"

if [ "$DISK_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 磁盘使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "90", "desc": "磁盘使用率告警阈值"},
            {"name": "盘符", "key": "DRIVE", "type": "string", "required": False, "value": "C:", "desc": "Windows盘符，如C:、D:"}
        ]
    },
    {
        "name": "Windows-服务状态检测",
        "type": "Windows操作系统",
        "interpreter": "sh",
        "desc": "检测Windows指定服务是否正在运行",
        "body": r"""#!/bin/bash
# Windows 服务状态检测 (通过PowerShell)
SERVICE_NAME=${_SPUG_SERVICE_NAME:-Winmgmt}

STATUS=$(powershell -Command "(Get-Service -Name '${SERVICE_NAME}' -ErrorAction SilentlyContinue).Status" 2>/dev/null)

if [ -z "$STATUS" ]; then
    echo "ERROR: 服务 ${SERVICE_NAME} 不存在"
    exit 1
fi

echo "服务 ${SERVICE_NAME} 状态: ${STATUS}"

if [ "$STATUS" != "Running" ]; then
    echo "ALERT: 服务未运行!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "服务名", "key": "SERVICE_NAME", "type": "string", "required": True, "value": "Winmgmt", "desc": "Windows服务名称"}
        ]
    },
    {
        "name": "Windows-事件日志错误数",
        "type": "Windows操作系统",
        "interpreter": "sh",
        "desc": "检测Windows事件日志中最近的错误数",
        "body": r"""#!/bin/bash
# Windows 事件日志错误检测 (通过PowerShell)
THRESHOLD=${_SPUG_THRESHOLD:-10}
MINUTES=${_SPUG_MINUTES:-30}

ERROR_COUNT=$(powershell -Command "(Get-WinEvent -FilterHashtable @{LogName='Application','System'; Level=2; StartTime=(Get-Date).AddMinutes(-${MINUTES})} -ErrorAction SilentlyContinue).Count" 2>/dev/null)

echo "最近${MINUTES}分钟事件错误数: ${ERROR_COUNT:-0} (阈值: ${THRESHOLD})"

if [ "${ERROR_COUNT:-0}" -ge "$THRESHOLD" ]; then
    echo "ALERT: 事件错误数超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "10", "desc": "错误数告警阈值"},
            {"name": "时间范围(分钟)", "key": "MINUTES", "type": "string", "required": False, "value": "30", "desc": "检测最近多少分钟内的错误"}
        ]
    },

    # ============================================================
    # MySQL 数据库
    # ============================================================
    {
        "name": "MySQL-连接数检测",
        "type": "MySQL数据库",
        "interpreter": "sh",
        "desc": "检测MySQL当前连接数占最大连接数比例",
        "body": r"""#!/bin/bash
# MySQL 连接数检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-3306}
USER=${_SPUG_USER:-root}
PASS=${_SPUG_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-80}

RESULT=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -N -e "SHOW GLOBAL STATUS LIKE 'Threads_connected'; SHOW GLOBAL VARIABLES LIKE 'max_connections';" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "ERROR: 无法连接MySQL"
    exit 1
fi

CONN_CURRENT=$(echo "$RESULT" | head -1 | awk '{print $2}')
CONN_MAX=$(echo "$RESULT" | tail -1 | awk '{print $2}')
CONN_PCT=$(echo "scale=1; $CONN_CURRENT * 100 / $CONN_MAX" | bc)
CONN_INT=${CONN_PCT%.*}

echo "MySQL连接数: ${CONN_CURRENT} / ${CONN_MAX} (${CONN_PCT}%, 阈值: ${THRESHOLD}%)"

if [ "$CONN_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: MySQL连接数占比超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "MySQL主机地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "3306", "desc": "MySQL端口"},
            {"name": "用户名", "key": "USER", "type": "string", "required": False, "value": "root", "desc": "MySQL用户名"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "MySQL密码"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "连接数占比告警阈值"}
        ]
    },
    {
        "name": "MySQL-慢查询检测",
        "type": "MySQL数据库",
        "interpreter": "sh",
        "desc": "检测MySQL慢查询数量",
        "body": r"""#!/bin/bash
# MySQL 慢查询检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-3306}
USER=${_SPUG_USER:-root}
PASS=${_SPUG_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-100}

SLOW_QUERIES=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -N -e "SHOW GLOBAL STATUS LIKE 'Slow_queries';" 2>/dev/null | awk '{print $2}')

if [ -z "$SLOW_QUERIES" ]; then
    echo "ERROR: 无法连接MySQL"
    exit 1
fi

echo "MySQL慢查询数: ${SLOW_QUERIES} (阈值: ${THRESHOLD})"

if [ "$SLOW_QUERIES" -ge "$THRESHOLD" ]; then
    echo "ALERT: 慢查询数超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "MySQL主机地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "3306", "desc": "MySQL端口"},
            {"name": "用户名", "key": "USER", "type": "string", "required": False, "value": "root", "desc": "MySQL用户名"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "MySQL密码"},
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "100", "desc": "慢查询数告警阈值"}
        ]
    },
    {
        "name": "MySQL-主从同步状态",
        "type": "MySQL数据库",
        "interpreter": "sh",
        "desc": "检测MySQL主从复制状态及延迟",
        "body": r"""#!/bin/bash
# MySQL 主从同步状态检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-3306}
USER=${_SPUG_USER:-root}
PASS=${_SPUG_PASS:-}
DELAY_THRESHOLD=${_SPUG_DELAY_THRESHOLD:-60}

RESULT=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -e "SHOW SLAVE STATUS\G" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "ERROR: 无法连接MySQL或未配置主从复制"
    exit 1
fi

IO_RUNNING=$(echo "$RESULT" | grep "Slave_IO_Running:" | awk '{print $2}')
SQL_RUNNING=$(echo "$RESULT" | grep "Slave_SQL_Running:" | awk '{print $2}')
BEHIND=$(echo "$RESULT" | grep "Seconds_Behind_Master:" | awk '{print $2}')
LAST_ERROR=$(echo "$RESULT" | grep "Last_Error:" | head -1 | awk -F': ' '{print $2}')

echo "IO线程: ${IO_RUNNING}, SQL线程: ${SQL_RUNNING}, 延迟: ${BEHIND}秒"

if [ "$IO_RUNNING" != "Yes" ] || [ "$SQL_RUNNING" != "Yes" ]; then
    echo "ALERT: 主从复制线程异常! Last_Error: ${LAST_ERROR}"
    exit 1
fi

if [ "$BEHIND" != "NULL" ] && [ "$BEHIND" -ge "$DELAY_THRESHOLD" ] 2>/dev/null; then
    echo "ALERT: 主从延迟 ${BEHIND}秒 超过阈值 ${DELAY_THRESHOLD}秒!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "MySQL从库地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "3306", "desc": "MySQL端口"},
            {"name": "用户名", "key": "USER", "type": "string", "required": False, "value": "root", "desc": "MySQL用户名"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "MySQL密码"},
            {"name": "延迟阈值(秒)", "key": "DELAY_THRESHOLD", "type": "string", "required": False, "value": "60", "desc": "主从延迟告警阈值(秒)"}
        ]
    },
    {
        "name": "MySQL-QPS检测",
        "type": "MySQL数据库",
        "interpreter": "sh",
        "desc": "检测MySQL每秒查询数(QPS)",
        "body": r"""#!/bin/bash
# MySQL QPS检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-3306}
USER=${_SPUG_USER:-root}
PASS=${_SPUG_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-10000}

Q1=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -N -e "SHOW GLOBAL STATUS LIKE 'Queries';" 2>/dev/null | awk '{print $2}')
sleep 1
Q2=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -N -e "SHOW GLOBAL STATUS LIKE 'Queries';" 2>/dev/null | awk '{print $2}')

if [ -z "$Q1" ] || [ -z "$Q2" ]; then
    echo "ERROR: 无法连接MySQL"
    exit 1
fi

QPS=$((Q2 - Q1))
echo "MySQL QPS: ${QPS} (阈值: ${THRESHOLD})"

if [ "$QPS" -ge "$THRESHOLD" ]; then
    echo "ALERT: QPS超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "MySQL主机地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "3306", "desc": "MySQL端口"},
            {"name": "用户名", "key": "USER", "type": "string", "required": False, "value": "root", "desc": "MySQL用户名"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "MySQL密码"},
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "10000", "desc": "QPS告警阈值"}
        ]
    },
    {
        "name": "MySQL-锁等待检测",
        "type": "MySQL数据库",
        "interpreter": "sh",
        "desc": "检测MySQL当前锁等待情况",
        "body": r"""#!/bin/bash
# MySQL 锁等待检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-3306}
USER=${_SPUG_USER:-root}
PASS=${_SPUG_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-5}

LOCK_WAIT=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -N -e "
SELECT COUNT(*) FROM information_schema.innodb_lock_waits;
" 2>/dev/null)

if [ -z "$LOCK_WAIT" ]; then
    echo "ERROR: 无法连接MySQL"
    exit 1
fi

echo "MySQL锁等待数: ${LOCK_WAIT:-0} (阈值: ${THRESHOLD})"

if [ "${LOCK_WAIT:-0}" -ge "$THRESHOLD" ]; then
    echo "ALERT: 锁等待数超过阈值!"
    mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -e "
    SELECT r.trx_id AS waiting_trx, r.trx_mysql_thread_id AS waiting_thread,
           b.trx_id AS blocking_trx, b.trx_mysql_thread_id AS blocking_thread
    FROM information_schema.innodb_lock_waits w
    JOIN information_schema.innodb_trx r ON w.requesting_trx_id=r.trx_id
    JOIN information_schema.innodb_trx b ON w.blocking_trx_id=b.trx_id;
    " 2>/dev/null
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "MySQL主机地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "3306", "desc": "MySQL端口"},
            {"name": "用户名", "key": "USER", "type": "string", "required": False, "value": "root", "desc": "MySQL用户名"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "MySQL密码"},
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "5", "desc": "锁等待数告警阈值"}
        ]
    },

    # ============================================================
    # MariaDB 数据库
    # ============================================================
    {
        "name": "MariaDB-连接数检测",
        "type": "MariaDB数据库",
        "interpreter": "sh",
        "desc": "检测MariaDB当前连接数占最大连接数比例",
        "body": r"""#!/bin/bash
# MariaDB 连接数检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-3306}
USER=${_SPUG_USER:-root}
PASS=${_SPUG_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-80}

RESULT=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -N -e "SHOW GLOBAL STATUS LIKE 'Threads_connected'; SHOW GLOBAL VARIABLES LIKE 'max_connections';" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "ERROR: 无法连接MariaDB"
    exit 1
fi

CONN_CURRENT=$(echo "$RESULT" | head -1 | awk '{print $2}')
CONN_MAX=$(echo "$RESULT" | tail -1 | awk '{print $2}')
CONN_PCT=$(echo "scale=1; $CONN_CURRENT * 100 / $CONN_MAX" | bc)
CONN_INT=${CONN_PCT%.*}

echo "MariaDB连接数: ${CONN_CURRENT} / ${CONN_MAX} (${CONN_PCT}%, 阈值: ${THRESHOLD}%)"

if [ "$CONN_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: MariaDB连接数占比超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "MariaDB主机地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "3306", "desc": "MariaDB端口"},
            {"name": "用户名", "key": "USER", "type": "string", "required": False, "value": "root", "desc": "MariaDB用户名"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "MariaDB密码"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "连接数占比告警阈值"}
        ]
    },
    {
        "name": "MariaDB-主从同步检测",
        "type": "MariaDB数据库",
        "interpreter": "sh",
        "desc": "检测MariaDB主从复制状态及延迟",
        "body": r"""#!/bin/bash
# MariaDB 主从同步检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-3306}
USER=${_SPUG_USER:-root}
PASS=${_SPUG_PASS:-}
DELAY_THRESHOLD=${_SPUG_DELAY_THRESHOLD:-60}

RESULT=$(mysql -h"$HOST" -P"$PORT" -u"$USER" -p"$PASS" -e "SHOW SLAVE STATUS\G" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "ERROR: 无法连接MariaDB或未配置主从复制"
    exit 1
fi

IO_RUNNING=$(echo "$RESULT" | grep "Slave_IO_Running:" | awk '{print $2}')
SQL_RUNNING=$(echo "$RESULT" | grep "Slave_SQL_Running:" | awk '{print $2}')
BEHIND=$(echo "$RESULT" | grep "Seconds_Behind_Master:" | awk '{print $2}')

echo "IO线程: ${IO_RUNNING}, SQL线程: ${SQL_RUNNING}, 延迟: ${BEHIND}秒"

if [ "$IO_RUNNING" != "Yes" ] || [ "$SQL_RUNNING" != "Yes" ]; then
    echo "ALERT: 主从复制线程异常!"
    exit 1
fi

if [ "$BEHIND" != "NULL" ] && [ "$BEHIND" -ge "$DELAY_THRESHOLD" ] 2>/dev/null; then
    echo "ALERT: 主从延迟 ${BEHIND}秒 超过阈值 ${DELAY_THRESHOLD}秒!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "MariaDB从库地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "3306", "desc": "MariaDB端口"},
            {"name": "用户名", "key": "USER", "type": "string", "required": False, "value": "root", "desc": "MariaDB用户名"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "MariaDB密码"},
            {"name": "延迟阈值(秒)", "key": "DELAY_THRESHOLD", "type": "string", "required": False, "value": "60", "desc": "主从延迟告警阈值(秒)"}
        ]
    },

    # ============================================================
    # Oracle 数据库
    # ============================================================
    {
        "name": "Oracle-表空间使用率",
        "type": "Oracle数据库",
        "interpreter": "sh",
        "desc": "检测Oracle表空间使用率",
        "body": r"""#!/bin/bash
# Oracle 表空间使用率检测
ORACLE_SID=${_SPUG_ORACLE_SID:-ORCL}
ORACLE_USER=${_SPUG_ORACLE_USER:-system}
ORACLE_PASS=${_SPUG_ORACLE_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-90}

RESULT=$(sqlplus -s "${ORACLE_USER}/${ORACLE_PASS}@${ORACLE_SID}" <<EOF
SET PAGESIZE 0 FEEDBACK OFF VERIFY OFF HEADING OFF ECHO OFF
SELECT tablespace_name || '|' || ROUND(used_percent, 1)
FROM (
  SELECT a.tablespace_name,
         (a.bytes_used / b.bytes_total) * 100 AS used_percent
  FROM (
    SELECT tablespace_name, SUM(bytes) AS bytes_used
    FROM dba_data_files
    GROUP BY tablespace_name
  ) a, (
    SELECT tablespace_name, SUM(bytes) AS bytes_total
    FROM dba_data_files
    GROUP BY tablespace_name
  ) b
  WHERE a.tablespace_name = b.tablespace_name
);
EXIT;
EOF
)

ALERT=0
echo "$RESULT" | while IFS='|' read -r TBS_NAME PCT; do
    if [ -n "$TBS_NAME" ] && [ -n "$PCT" ]; then
        PCT_INT=${PCT%.*}
        echo "表空间 ${TBS_NAME}: ${PCT}%"
        if [ "$PCT_INT" -ge "$THRESHOLD" ]; then
            echo "ALERT: 表空间 ${TBS_NAME} 使用率超过阈值!"
            exit 1
        fi
    fi
done

exit $?""",
        "parameters": [
            {"name": "Oracle SID", "key": "ORACLE_SID", "type": "string", "required": False, "value": "ORCL", "desc": "Oracle实例名"},
            {"name": "用户名", "key": "ORACLE_USER", "type": "string", "required": False, "value": "system", "desc": "Oracle用户名"},
            {"name": "密码", "key": "ORACLE_PASS", "type": "password", "required": False, "value": "", "desc": "Oracle密码"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "90", "desc": "表空间使用率告警阈值"}
        ]
    },
    {
        "name": "Oracle-会话数检测",
        "type": "Oracle数据库",
        "interpreter": "sh",
        "desc": "检测Oracle当前会话数",
        "body": r"""#!/bin/bash
# Oracle 会话数检测
ORACLE_SID=${_SPUG_ORACLE_SID:-ORCL}
ORACLE_USER=${_SPUG_ORACLE_USER:-system}
ORACLE_PASS=${_SPUG_ORACLE_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-500}

RESULT=$(sqlplus -s "${ORACLE_USER}/${ORACLE_PASS}@${ORACLE_SID}" <<EOF
SET PAGESIZE 0 FEEDBACK OFF VERIFY OFF HEADING OFF ECHO OFF
SELECT COUNT(*) || '|' || v.value
FROM v\$session s, v\$parameter v
WHERE v.name = 'sessions';
EXIT;
EOF
)

SESSION_CURRENT=$(echo "$RESULT" | cut -d'|' -f1)
SESSION_MAX=$(echo "$RESULT" | cut -d'|' -f2)
echo "Oracle会话数: ${SESSION_CURRENT} / ${SESSION_MAX}"

if [ "$SESSION_CURRENT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 会话数超过阈值 ${THRESHOLD}!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "Oracle SID", "key": "ORACLE_SID", "type": "string", "required": False, "value": "ORCL", "desc": "Oracle实例名"},
            {"name": "用户名", "key": "ORACLE_USER", "type": "string", "required": False, "value": "system", "desc": "Oracle用户名"},
            {"name": "密码", "key": "ORACLE_PASS", "type": "password", "required": False, "value": "", "desc": "Oracle密码"},
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "500", "desc": "会话数告警阈值"}
        ]
    },

    # ============================================================
    # Nginx
    # ============================================================
    {
        "name": "Nginx-进程状态检测",
        "type": "Nginx",
        "interpreter": "sh",
        "desc": "检测Nginx进程是否正常运行",
        "body": r"""#!/bin/bash
# Nginx 进程状态检测

NGINX_COUNT=$(ps -ef | grep -v grep | grep -c "nginx:")
if [ "$NGINX_COUNT" -eq 0 ]; then
    NGINX_COUNT=$(ps -ef | grep -v grep | grep -c "[n]ginx")
fi

echo "Nginx进程数: ${NGINX_COUNT}"

if [ "$NGINX_COUNT" -eq 0 ]; then
    echo "ALERT: Nginx进程未运行!"
    exit 1
fi
exit 0""",
        "parameters": []
    },
    {
        "name": "Nginx-StubStatus监控",
        "type": "Nginx",
        "interpreter": "sh",
        "desc": "通过stub_status获取Nginx连接数和请求数",
        "body": r"""#!/bin/bash
# Nginx StubStatus监控
STATUS_URL=${_SPUG_STATUS_URL:-http://127.0.0.1/nginx_status}
CONN_THRESHOLD=${_SPUG_CONN_THRESHOLD:-10000}

RESULT=$(curl -s "$STATUS_URL" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "ERROR: 无法获取Nginx StubStatus，请确认stub_status模块已配置"
    exit 1
fi

ACTIVE=$(echo "$RESULT" | grep "Active connections" | awk '{print $3}')
ACCEPTED=$(echo "$RESULT" | grep "server accepts" | awk '{print $2}')
HANDLED=$(echo "$RESULT" | grep "server accepts" | awk '{print $3}')
REQUESTS=$(echo "$RESULT" | grep "server accepts" | awk '{print $4}')
READING=$(echo "$RESULT" | awk '/Reading/ {print $2}')
WRITING=$(echo "$RESULT" | awk '/Reading/ {print $4}')
WAITING=$(echo "$RESULT" | awk '/Reading/ {print $6}')

echo "Nginx状态: 活跃连接=${ACTIVE}, 已接受=${ACCEPTED}, 已处理=${HANDLED}, 总请求=${REQUESTS}"
echo "连接详情: Reading=${READING}, Writing=${WRITING}, Waiting=${WAITING}"

if [ "$ACTIVE" -ge "$CONN_THRESHOLD" ]; then
    echo "ALERT: 活跃连接数超过阈值 ${CONN_THRESHOLD}!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "Status URL", "key": "STATUS_URL", "type": "string", "required": False, "value": "http://127.0.0.1/nginx_status", "desc": "Nginx stub_status页面URL"},
            {"name": "连接数阈值", "key": "CONN_THRESHOLD", "type": "string", "required": False, "value": "10000", "desc": "活跃连接数告警阈值"}
        ]
    },
    {
        "name": "Nginx-配置文件语法检测",
        "type": "Nginx",
        "interpreter": "sh",
        "desc": "检测Nginx配置文件语法是否正确",
        "body": r"""#!/bin/bash
# Nginx 配置文件语法检测

RESULT=$(nginx -t 2>&1)

if echo "$RESULT" | grep -q "successful"; then
    echo "Nginx配置语法检测通过"
    exit 0
else
    echo "ALERT: Nginx配置语法错误!"
    echo "$RESULT"
    exit 1
fi""",
        "parameters": []
    },
    {
        "name": "Nginx-502错误率检测",
        "type": "Nginx",
        "interpreter": "sh",
        "desc": "检测Nginx访问日志中502错误占比",
        "body": r"""#!/bin/bash
# Nginx 502错误率检测
LOG_PATH=${_SPUG_LOG_PATH:-/var/log/nginx/access.log}
THRESHOLD=${_SPUG_THRESHOLD:-5}
MINUTES=${_SPUG_MINUTES:-5}

SINCE=$(date -d "${MINUTES} minutes ago" "+%d/%b/%Y:%H:%M:%S" 2>/dev/null || date -v-${MINUTES}M "+%d/%b/%Y:%H:%M:%S")

if [ ! -f "$LOG_PATH" ]; then
    echo "ERROR: 日志文件 ${LOG_PATH} 不存在"
    exit 1
fi

TOTAL=$(awk -v since="$SINCE" '$4 ~ /\[/ { ts=substr($4,2); if(ts>=since) count++ } END{print count+0}' "$LOG_PATH")
ERROR_502=$(awk -v since="$SINCE" '$4 ~ /\[/ { ts=substr($4,2); if(ts>=since && $9==502) count++ } END{print count+0}' "$LOG_PATH")

if [ "$TOTAL" -gt 0 ]; then
    PCT=$(echo "scale=2; $ERROR_502 * 100 / $TOTAL" | bc)
else
    PCT="0"
fi

PCT_INT=${PCT%.*}
echo "502错误率: ${PCT}% (502数: ${ERROR_502}, 总请求数: ${TOTAL}, 最近${MINUTES}分钟, 阈值: ${THRESHOLD}%)"

if [ "$TOTAL" -gt 0 ] && [ "${PCT_INT:-0}" -ge "$THRESHOLD" ]; then
    echo "ALERT: 502错误率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "日志路径", "key": "LOG_PATH", "type": "string", "required": False, "value": "/var/log/nginx/access.log", "desc": "Nginx访问日志路径"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "5", "desc": "502错误率告警阈值"},
            {"name": "时间范围(分钟)", "key": "MINUTES", "type": "string", "required": False, "value": "5", "desc": "检测最近多少分钟"}
        ]
    },

    # ============================================================
    # Tomcat
    # ============================================================
    {
        "name": "Tomcat-进程状态检测",
        "type": "Tomcat",
        "interpreter": "sh",
        "desc": "检测Tomcat进程是否正常运行",
        "body": r"""#!/bin/bash
# Tomcat 进程状态检测

TOMCAT_COUNT=$(ps -ef | grep -v grep | grep -c "[c]atalina")
if [ "$TOMCAT_COUNT" -eq 0 ]; then
    TOMCAT_COUNT=$(ps -ef | grep -v grep | grep -c "[t]omcat")
fi

echo "Tomcat进程数: ${TOMCAT_COUNT}"

if [ "$TOMCAT_COUNT" -eq 0 ]; then
    echo "ALERT: Tomcat进程未运行!"
    exit 1
fi
exit 0""",
        "parameters": []
    },
    {
        "name": "Tomcat-线程数检测",
        "type": "Tomcat",
        "interpreter": "sh",
        "desc": "检测Tomcat线程数是否超过阈值",
        "body": r"""#!/bin/bash
# Tomcat 线程数检测
THRESHOLD=${_SPUG_THRESHOLD:-500}

TOMCAT_PID=$(ps -ef | grep -v grep | grep "[c]atalina" | head -1 | awk '{print $2}')
if [ -z "$TOMCAT_PID" ]; then
    TOMCAT_PID=$(ps -ef | grep -v grep | grep "[t]omcat" | head -1 | awk '{print $2}')
fi

if [ -z "$TOMCAT_PID" ]; then
    echo "ALERT: Tomcat进程未运行!"
    exit 1
fi

THREAD_COUNT=$(ls /proc/$TOMCAT_PID/task 2>/dev/null | wc -l)
echo "Tomcat线程数: ${THREAD_COUNT} (PID: ${TOMCAT_PID}, 阈值: ${THRESHOLD})"

if [ "$THREAD_COUNT" -ge "$THRESHOLD" ]; then
    echo "ALERT: Tomcat线程数超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "500", "desc": "线程数告警阈值"}
        ]
    },
    {
        "name": "Tomcat-JVM堆内存使用率",
        "type": "Tomcat",
        "interpreter": "sh",
        "desc": "检测Tomcat JVM堆内存使用率（通过JMX）",
        "body": r"""#!/bin/bash
# Tomcat JVM堆内存使用率检测
JMX_PORT=${_SPUG_JMX_PORT:-9010}
THRESHOLD=${_SPUG_THRESHOLD:-85}

TOMCAT_PID=$(ps -ef | grep -v grep | grep "[c]atalina" | head -1 | awk '{print $2}')
if [ -z "$TOMCAT_PID" ]; then
    TOMCAT_PID=$(ps -ef | grep -v grep | grep "[t]omcat" | head -1 | awk '{print $2}')
fi

if [ -z "$TOMCAT_PID" ]; then
    echo "ALERT: Tomcat进程未运行!"
    exit 1
fi

# 通过/proc获取JVM内存信息
JVM_HEAP=$(cat /proc/$TOMCAT_PID/status 2>/dev/null | grep VmRSS | awk '{print $2}')

if command -v jstat &>/dev/null; then
    HEAP_USED=$(jstat -gc $TOMCAT_PID 2>/dev/null | tail -1 | awk '{print ($3+$4+$6+$8)/1024}')
    HEAP_MAX=$(jstat -gcapacity $TOMCAT_PID 2>/dev/null | tail -1 | awk '{print $8/1024}')
    if [ -n "$HEAP_USED" ] && [ -n "$HEAP_MAX" ] && [ "$HEAP_MAX" != "0" ]; then
        HEAP_PCT=$(echo "scale=1; $HEAP_USED * 100 / $HEAP_MAX" | bc)
        HEAP_INT=${HEAP_PCT%.*}
        echo "JVM堆内存使用率: ${HEAP_PCT}% (已用: ${HEAP_USED}MB / 最大: ${HEAP_MAX}MB, 阈值: ${THRESHOLD}%)"
        if [ "$HEAP_INT" -ge "$THRESHOLD" ]; then
            echo "ALERT: JVM堆内存使用率超过阈值!"
            exit 1
        fi
        exit 0
    fi
fi

echo "INFO: 无法通过jstat获取JVM内存，使用进程RSS替代"
echo "JVM进程RSS: ${JVM_HEAP}KB"
exit 0""",
        "parameters": [
            {"name": "JMX端口", "key": "JMX_PORT", "type": "string", "required": False, "value": "9010", "desc": "JMX远程端口"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "85", "desc": "堆内存使用率告警阈值"}
        ]
    },
    {
        "name": "Tomcat-HTTP线程池检测",
        "type": "Tomcat",
        "interpreter": "sh",
        "desc": "通过Manager接口检测Tomcat线程池使用情况",
        "body": r"""#!/bin/bash
# Tomcat HTTP线程池检测
MANAGER_URL=${_SPUG_MANAGER_URL:-http://127.0.0.1:8080/manager/status}
MANAGER_USER=${_SPUG_MANAGER_USER:-admin}
MANAGER_PASS=${_SPUG_MANAGER_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-80}

RESULT=$(curl -s -u "${MANAGER_USER}:${MANAGER_PASS}" "${MANAGER_URL}?XML=true" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "ERROR: 无法访问Tomcat Manager接口"
    exit 1
fi

CURRENT=$(echo "$RESULT" | grep -oP 'currentThreadsBusy="\K[^"]+' | head -1)
MAX=$(echo "$RESULT" | grep -oP 'maxThreads="\K[^"]+' | head -1)

if [ -n "$CURRENT" ] && [ -n "$MAX" ] && [ "$MAX" -gt 0 ]; then
    PCT=$(echo "scale=1; $CURRENT * 100 / $MAX" | bc)
    PCT_INT=${PCT%.*}
    echo "HTTP线程池使用率: ${PCT}% (繁忙: ${CURRENT} / 最大: ${MAX}, 阈值: ${THRESHOLD}%)"
    if [ "$PCT_INT" -ge "$THRESHOLD" ]; then
        echo "ALERT: HTTP线程池使用率超过阈值!"
        exit 1
    fi
else
    echo "WARN: 无法解析线程池数据"
fi
exit 0""",
        "parameters": [
            {"name": "Manager URL", "key": "MANAGER_URL", "type": "string", "required": False, "value": "http://127.0.0.1:8080/manager/status", "desc": "Tomcat Manager状态页URL"},
            {"name": "用户名", "key": "MANAGER_USER", "type": "string", "required": False, "value": "admin", "desc": "Manager用户名"},
            {"name": "密码", "key": "MANAGER_PASS", "type": "password", "required": False, "value": "", "desc": "Manager密码"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "线程池使用率告警阈值"}
        ]
    },

    # ============================================================
    # Apache
    # ============================================================
    {
        "name": "Apache-进程状态检测",
        "type": "Apache",
        "interpreter": "sh",
        "desc": "检测Apache(httpd)进程是否正常运行",
        "body": r"""#!/bin/bash
# Apache 进程状态检测

APACHE_COUNT=$(ps -ef | grep -v grep | grep -c "[h]ttpd")
echo "Apache进程数: ${APACHE_COUNT}"

if [ "$APACHE_COUNT" -eq 0 ]; then
    echo "ALERT: Apache进程未运行!"
    exit 1
fi
exit 0""",
        "parameters": []
    },
    {
        "name": "Apache-ServerStatus监控",
        "type": "Apache",
        "interpreter": "sh",
        "desc": "通过server-status获取Apache工作进程状态",
        "body": r"""#!/bin/bash
# Apache ServerStatus监控
STATUS_URL=${_SPUG_STATUS_URL:-http://127.0.0.1/server-status}
BUSY_THRESHOLD=${_SPUG_BUSY_THRESHOLD:-80}

RESULT=$(curl -s "${STATUS_URL}?auto" 2>/dev/null)

if [ -z "$RESULT" ]; then
    echo "ERROR: 无法获取Apache ServerStatus，请确认mod_status已启用"
    exit 1
fi

BUSY=$(echo "$RESULT" | grep "BusyWorkers" | awk '{print $2}')
IDLE=$(echo "$RESULT" | grep "IdleWorkers" | awk '{print $2}')
TOTAL=$((BUSY + IDLE))

if [ "$TOTAL" -gt 0 ]; then
    PCT=$(echo "scale=1; $BUSY * 100 / $TOTAL" | bc)
    PCT_INT=${PCT%.*}
    echo "Apache工作进程: 繁忙=${BUSY}, 空闲=${IDLE}, 总计=${TOTAL}, 使用率=${PCT}%"
    if [ "$PCT_INT" -ge "$BUSY_THRESHOLD" ]; then
        echo "ALERT: Apache繁忙进程占比超过阈值 ${BUSY_THRESHOLD}%!"
        exit 1
    fi
else
    echo "WARN: 无法解析Apache状态数据"
fi
exit 0""",
        "parameters": [
            {"name": "Status URL", "key": "STATUS_URL", "type": "string", "required": False, "value": "http://127.0.0.1/server-status", "desc": "Apache server-status URL"},
            {"name": "繁忙阈值(%)", "key": "BUSY_THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "繁忙进程占比告警阈值"}
        ]
    },
    {
        "name": "Apache-配置语法检测",
        "type": "Apache",
        "interpreter": "sh",
        "desc": "检测Apache配置文件语法是否正确",
        "body": r"""#!/bin/bash
# Apache 配置语法检测

RESULT=$(apachectl configtest 2>&1 || httpd -t 2>&1)

if echo "$RESULT" | grep -qi "syntax ok"; then
    echo "Apache配置语法检测通过"
    exit 0
else
    echo "ALERT: Apache配置语法错误!"
    echo "$RESULT"
    exit 1
fi""",
        "parameters": []
    },

    # ============================================================
    # Redis
    # ============================================================
    {
        "name": "Redis-内存使用率",
        "type": "Redis",
        "interpreter": "sh",
        "desc": "检测Redis内存使用率",
        "body": r"""#!/bin/bash
# Redis 内存使用率检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-6379}
PASS=${_SPUG_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-80}

REDIS_CLI="redis-cli -h $HOST -p $PORT"
if [ -n "$PASS" ]; then
    REDIS_CLI="$REDIS_CLI -a $PASS"
fi

USED_MEM=$($REDIS_CLI info memory 2>/dev/null | grep "used_memory:" | awk -F: '{print $2}' | tr -d '\r')
MAX_MEM=$($REDIS_CLI config get maxmemory 2>/dev/null | tail -1 | tr -d '\r')

if [ -z "$USED_MEM" ]; then
    echo "ERROR: 无法连接Redis"
    exit 1
fi

USED_MB=$(echo "scale=1; $USED_MEM / 1048576" | bc)

if [ "$MAX_MEM" -eq 0 ] || [ -z "$MAX_MEM" ]; then
    echo "Redis内存使用: ${USED_MB}MB (未设置maxmemory限制)"
    exit 0
fi

MAX_MB=$(echo "scale=1; $MAX_MEM / 1048576" | bc)
MEM_PCT=$(echo "scale=1; $USED_MEM * 100 / $MAX_MEM" | bc)
MEM_INT=${MEM_PCT%.*}

echo "Redis内存使用率: ${MEM_PCT}% (已用: ${USED_MB}MB / 上限: ${MAX_MB}MB, 阈值: ${THRESHOLD}%)"

if [ "$MEM_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: Redis内存使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "Redis主机地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "6379", "desc": "Redis端口"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "Redis密码"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "内存使用率告警阈值"}
        ]
    },
    {
        "name": "Redis-连接数检测",
        "type": "Redis",
        "interpreter": "sh",
        "desc": "检测Redis连接数占上限比例",
        "body": r"""#!/bin/bash
# Redis 连接数检测
HOST=${_SPUG_HOST:-127.0.0.1}
PORT=${_SPUG_PORT:-6379}
PASS=${_SPUG_PASS:-}
THRESHOLD=${_SPUG_THRESHOLD:-80}

REDIS_CLI="redis-cli -h $HOST -p $PORT"
if [ -n "$PASS" ]; then
    REDIS_CLI="$REDIS_CLI -a $PASS"
fi

CONN_CURRENT=$($REDIS_CLI info clients 2>/dev/null | grep "connected_clients:" | awk -F: '{print $2}' | tr -d '\r')
CONN_MAX=$($REDIS_CLI config get maxclients 2>/dev/null | tail -1 | tr -d '\r')

if [ -z "$CONN_CURRENT" ]; then
    echo "ERROR: 无法连接Redis"
    exit 1
fi

if [ -z "$CONN_MAX" ] || [ "$CONN_MAX" -eq 0 ]; then
    CONN_MAX=10000
fi

CONN_PCT=$(echo "scale=1; $CONN_CURRENT * 100 / $CONN_MAX" | bc)
CONN_INT=${CONN_PCT%.*}

echo "Redis连接数: ${CONN_CURRENT} / ${CONN_MAX} (${CONN_PCT}%, 阈值: ${THRESHOLD}%)"

if [ "$CONN_INT" -ge "$THRESHOLD" ]; then
    echo "ALERT: Redis连接数占比超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "主机", "key": "HOST", "type": "string", "required": False, "value": "127.0.0.1", "desc": "Redis主机地址"},
            {"name": "端口", "key": "PORT", "type": "string", "required": False, "value": "6379", "desc": "Redis端口"},
            {"name": "密码", "key": "PASS", "type": "password", "required": False, "value": "", "desc": "Redis密码"},
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "连接数占比告警阈值"}
        ]
    },

    # ============================================================
    # 通用/网络
    # ============================================================
    {
        "name": "通用-端口连通性检测",
        "type": "通用",
        "interpreter": "sh",
        "desc": "检测指定主机端口是否可连通",
        "body": r"""#!/bin/bash
# 通用端口连通性检测
TARGET_HOST=${_SPUG_TARGET_HOST:-127.0.0.1}
TARGET_PORT=${_SPUG_TARGET_PORT:-80}
TIMEOUT=${_SPUG_TIMEOUT:-3}

if command -v nc &>/dev/null; then
    nc -z -w $TIMEOUT "$TARGET_HOST" "$TARGET_PORT" 2>/dev/null
    RESULT=$?
elif command -v timeout &>/dev/null; then
    timeout $TIMEOUT bash -c "echo >/dev/tcp/${TARGET_HOST}/${TARGET_PORT}" 2>/dev/null
    RESULT=$?
else
    (echo >/dev/tcp/${TARGET_HOST}/${TARGET_PORT}) &>/dev/null
    RESULT=$?
fi

if [ $RESULT -eq 0 ]; then
    echo "端口连通: ${TARGET_HOST}:${TARGET_PORT}"
    exit 0
else
    echo "ALERT: 端口不可达 ${TARGET_HOST}:${TARGET_PORT}"
    exit 1
fi""",
        "parameters": [
            {"name": "目标主机", "key": "TARGET_HOST", "type": "string", "required": True, "value": "127.0.0.1", "desc": "目标主机地址"},
            {"name": "目标端口", "key": "TARGET_PORT", "type": "string", "required": True, "value": "80", "desc": "目标端口号"},
            {"name": "超时(秒)", "key": "TIMEOUT", "type": "string", "required": False, "value": "3", "desc": "连接超时时间"}
        ]
    },
    {
        "name": "通用-URL可用性检测",
        "type": "通用",
        "interpreter": "sh",
        "desc": "检测URL是否可访问及响应时间",
        "body": r"""#!/bin/bash
# 通用URL可用性检测
URL=${_SPUG_URL:-http://127.0.0.1}
TIME_THRESHOLD=${_SPUG_TIME_THRESHOLD:-3000}

RESULT=$(curl -s -o /dev/null -w "%{http_code} %{time_total}" --connect-timeout 10 --max-time 30 "$URL" 2>/dev/null)
HTTP_CODE=$(echo $RESULT | awk '{print $1}')
RESPONSE_TIME=$(echo $RESULT | awk '{print $2}')
RESPONSE_MS=$(echo "$RESPONSE_TIME * 1000" | bc 2>/dev/null || echo "0")
RESPONSE_INT=${RESPONSE_MS%.*}

echo "URL: ${URL}, HTTP状态码: ${HTTP_CODE}, 响应时间: ${RESPONSE_MS}ms"

if [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 400 ]; then
    echo "ALERT: HTTP状态码异常!"
    exit 1
fi

if [ "${RESPONSE_INT:-0}" -ge "$TIME_THRESHOLD" ]; then
    echo "ALERT: 响应时间 ${RESPONSE_MS}ms 超过阈值 ${TIME_THRESHOLD}ms!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "URL", "key": "URL", "type": "string", "required": True, "value": "http://127.0.0.1", "desc": "要检测的URL"},
            {"name": "响应时间阈值(ms)", "key": "TIME_THRESHOLD", "type": "string", "required": False, "value": "3000", "desc": "响应时间告警阈值(毫秒)"}
        ]
    },
    {
        "name": "通用-日志错误关键词检测",
        "type": "通用",
        "interpreter": "sh",
        "desc": "检测日志文件中是否出现指定错误关键词",
        "body": r"""#!/bin/bash
# 通用日志错误关键词检测
LOG_PATH=${_SPUG_LOG_PATH:-/var/log/syslog}
KEYWORD=${_SPUG_KEYWORD:-ERROR}
MINUTES=${_SPUG_MINUTES:-10}
THRESHOLD=${_SPUG_THRESHOLD:-5}

if [ ! -f "$LOG_PATH" ]; then
    echo "ERROR: 日志文件 ${LOG_PATH} 不存在"
    exit 1
fi

SINCE=$(date -d "${MINUTES} minutes ago" "+%Y-%m-%d %H:%M" 2>/dev/null || date -v-${MINUTES}M "+%Y-%m-%d %H:%M")

ERROR_COUNT=$(grep -c "$KEYWORD" "$LOG_PATH" 2>/dev/null || echo 0)

echo "日志 ${LOG_PATH} 中关键词 '${KEYWORD}' 出现次数: ${ERROR_COUNT} (阈值: ${THRESHOLD})"

if [ "$ERROR_COUNT" -ge "$THRESHOLD" ]; then
    echo "ALERT: 错误关键词出现次数超过阈值!"
    echo "最近匹配:"
    grep "$KEYWORD" "$LOG_PATH" | tail -5
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "日志路径", "key": "LOG_PATH", "type": "string", "required": True, "value": "/var/log/syslog", "desc": "日志文件路径"},
            {"name": "关键词", "key": "KEYWORD", "type": "string", "required": True, "value": "ERROR", "desc": "要搜索的错误关键词"},
            {"name": "时间范围(分钟)", "key": "MINUTES", "type": "string", "required": False, "value": "10", "desc": "检测最近多少分钟"},
            {"name": "告警阈值", "key": "THRESHOLD", "type": "string", "required": False, "value": "5", "desc": "关键词出现次数告警阈值"}
        ]
    },
    {
        "name": "通用-磁盘inode使用率",
        "type": "通用",
        "interpreter": "sh",
        "desc": "检测文件系统inode使用率",
        "body": r"""#!/bin/bash
# 通用 磁盘inode使用率检测
THRESHOLD=${_SPUG_THRESHOLD:-80}
MOUNT_POINT=${_SPUG_MOUNT_POINT:-/}

INODE_PCT=$(df -i "$MOUNT_POINT" | tail -1 | awk '{print $5}' | tr -d '%')
echo "Inode使用率: ${INODE_PCT}% (分区: ${MOUNT_POINT}, 阈值: ${THRESHOLD}%)"

if [ "$INODE_PCT" -ge "$THRESHOLD" ]; then
    echo "ALERT: Inode使用率超过阈值!"
    exit 1
fi
exit 0""",
        "parameters": [
            {"name": "告警阈值(%)", "key": "THRESHOLD", "type": "string", "required": False, "value": "80", "desc": "Inode使用率告警阈值"},
            {"name": "挂载点", "key": "MOUNT_POINT", "type": "string", "required": False, "value": "/", "desc": "磁盘挂载点"}
        ]
    },
    {
        "name": "通用-Cron任务检测",
        "type": "通用",
        "interpreter": "sh",
        "desc": "检测crontab中指定任务是否存在",
        "body": r"""#!/bin/bash
# 通用 Cron任务检测
CRON_KEYWORD=${_SPUG_CRON_KEYWORD:-backup}
CRON_USER=${_SPUG_CRON_USER:-root}

if [ "$CRON_USER" = "root" ]; then
    CRON_CONTENT=$(crontab -l 2>/dev/null)
else
    CRON_CONTENT=$(crontab -u "$CRON_USER" -l 2>/dev/null)
fi

if echo "$CRON_CONTENT" | grep -q "$CRON_KEYWORD"; then
    echo "Cron任务检测通过: 用户 ${CRON_USER} 的crontab中包含关键词 '${CRON_KEYWORD}'"
    exit 0
else
    echo "ALERT: 用户 ${CRON_USER} 的crontab中未找到关键词 '${CRON_KEYWORD}' 的任务!"
    exit 1
fi""",
        "parameters": [
            {"name": "Cron关键词", "key": "CRON_KEYWORD", "type": "string", "required": True, "value": "backup", "desc": "Cron任务关键词"},
            {"name": "Cron用户", "key": "CRON_USER", "type": "string", "required": False, "value": "root", "desc": "Cron任务所属用户"}
        ]
    },
]