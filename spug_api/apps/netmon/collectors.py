# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
指标采集器
----------
统一返回格式: dict(metric_key -> float)，采集失败返回 None。
支持三种采集方式，覆盖网络设备/服务器/应用等主流场景：
  * ping  —— 时延(rtt)/丢包率(loss)，适用于任意可达的网络设备
  * snmp  —— 标准 MIB（HOST-RESOURCES-MIB / IF-MIB），适用于交换机/路由器/防火墙等网络设备
  * agent —— 复用 spug 已有主机凭据通过 SSH 采集 CPU/内存/磁盘/网卡，适用于已经纳管的服务器
"""
from django_redis import get_redis_connection
from statistics import mean
import subprocess
import platform
import logging
import time
import re

RDS_PREV_KEY = 'spug:netmon:prev:{}:{}'  # 上一次采样(用于网卡流量等计数器差值计算)


def _ping_once(addr, timeout=1):
    system = platform.system().lower()
    if system == 'windows':
        cmd = f'ping -n 1 -w {int(timeout * 1000)} {addr}'
    else:
        cmd = f'ping -c 1 -W {int(timeout)} {addr}'
    t0 = time.perf_counter()
    task = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    ok = task.returncode == 0
    if ok:
        out = task.stdout.decode(errors='ignore')
        m = re.search(r'time[=<]([\d.]+)', out) or re.search(r'时间[=<]([\d.]+)', out)
        rtt = float(m.group(1)) if m else round(elapsed_ms, 2)
        return True, rtt
    return False, None


def collect_ping(device, samples=4):
    ok_count, rtts = 0, []
    for _ in range(samples):
        ok, rtt = _ping_once(device.ip)
        if ok:
            ok_count += 1
            rtts.append(rtt)
    loss = round((samples - ok_count) / samples * 100, 2)
    result = {'loss': loss}
    if rtts:
        result['rtt'] = round(mean(rtts), 2)
    return result


def collect_snmp(device):
    """采集 CPU / 内存 / 磁盘 / 网卡流量，需要设备开启 SNMP 并配置好团体字"""
    try:
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
            ContextData, ObjectType, ObjectIdentity
        )
    except ImportError:
        logging.warning('pysnmp 未安装，无法执行 SNMP 采集，请 pip install pysnmp 后重试')
        return None

    # HOST-RESOURCES-MIB: hrProcessorLoad(.1.3.6.1.2.1.25.3.3.1.2)
    # UCD-SNMP-MIB(常见网络设备兼容): memTotalReal/memAvailReal
    oids = {
        'cpu': '1.3.6.1.2.1.25.3.3.1.2.1',
        'mem_total': '1.3.6.1.4.1.2021.4.5.0',
        'mem_avail': '1.3.6.1.4.1.2021.4.6.0',
        'if_in': '1.3.6.1.2.1.2.2.1.10.1',
        'if_out': '1.3.6.1.2.1.2.2.1.16.1',
    }
    result = {}
    for key, oid in oids.items():
        try:
            it = getCmd(
                SnmpEngine(),
                CommunityData(device.snmp_community, mpModel=0 if device.snmp_version == '1' else 1),
                UdpTransportTarget((device.ip, device.snmp_port), timeout=3, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            error_indication, error_status, _, var_binds = next(it)
            if error_indication or error_status:
                continue
            value = var_binds[0][1]
            result[key] = float(value)
        except Exception as e:
            logging.warning(f'SNMP采集异常 device={device.ip} oid={oid}: {e}')

    output = {}
    if 'cpu' in result:
        output['cpu'] = round(result['cpu'], 2)
    if 'mem_total' in result and 'mem_avail' in result and result['mem_total']:
        output['memory'] = round((1 - result['mem_avail'] / result['mem_total']) * 100, 2)
    if 'if_in' in result:
        output.update(_counter_rate(device, 'net_in', result['if_in']))
    if 'if_out' in result:
        output.update(_counter_rate(device, 'net_out', result['if_out']))
    return output or None


def _counter_rate(device, metric_key, counter_octets):
    """SNMP/Agent 采集到的都是累计计数器(字节数)，需要与上一次采样做差得到速率(Kbps)"""
    rds = get_redis_connection()
    key = RDS_PREV_KEY.format(device.id, metric_key)
    prev = rds.hgetall(key)
    now = time.time()
    rds.hset(key, mapping={'v': counter_octets, 't': now})
    rds.expire(key, 600)
    if not prev:
        return {}
    prev_v, prev_t = float(prev[b'v']), float(prev[b't'])
    dt = now - prev_t
    if dt <= 0 or counter_octets < prev_v:
        return {}
    kbps = round((counter_octets - prev_v) * 8 / 1024 / dt, 2)
    return {metric_key: kbps}


def collect_agent(device):
    """通过已纳管主机的 SSH 凭据采集 CPU/内存/磁盘/网卡（Linux）"""
    if not device.host_id:
        return None
    host = device.host
    script = (
        "echo '#CPU#'; grep 'cpu ' /proc/stat; sleep 0.3; grep 'cpu ' /proc/stat; "
        "echo '#MEM#'; free -m | grep Mem; "
        "echo '#DISK#'; df -h / | tail -1; "
        "echo '#NET#'; cat /proc/net/dev | grep -v 'lo:' | grep ':' | head -1"
    )
    try:
        with host.get_ssh() as ssh:
            exit_code, out = ssh.exec_command_raw(script)
        if exit_code != 0 or not out:
            return None
    except Exception as e:
        logging.warning(f'Agent采集异常 device={device.ip}: {e}')
        return None

    result = {}
    try:
        blocks = re.split(r'#(CPU|MEM|DISK|NET)#\s*', out)
        data = {blocks[i]: blocks[i + 1] for i in range(1, len(blocks) - 1, 2)}

        cpu_lines = [l for l in data.get('CPU', '').splitlines() if l.strip()]
        if len(cpu_lines) >= 2:
            c1 = [int(x) for x in cpu_lines[0].split()[1:]]
            c2 = [int(x) for x in cpu_lines[1].split()[1:]]
            idle1, idle2 = c1[3], c2[3]
            total1, total2 = sum(c1), sum(c2)
            dt, didle = total2 - total1, idle2 - idle1
            if dt > 0:
                result['cpu'] = round((1 - didle / dt) * 100, 2)

        mem_line = data.get('MEM', '').split()
        if len(mem_line) >= 3:
            total, used = float(mem_line[1]), float(mem_line[2])
            if total:
                result['memory'] = round(used / total * 100, 2)

        disk_line = data.get('DISK', '').split()
        if len(disk_line) >= 5:
            result['disk'] = float(disk_line[4].strip('%'))

        net_line = data.get('NET', '').split()
        if len(net_line) >= 10:
            rx_bytes = float(net_line[1])
            tx_bytes = float(net_line[9])
            result.update(_counter_rate(device, 'net_in', rx_bytes))
            result.update(_counter_rate(device, 'net_out', tx_bytes))
    except Exception as e:
        logging.warning(f'Agent数据解析异常 device={device.ip}: {e}')
    return result or None


def collect(device):
    """统一入口：根据设备配置的采集方式分发"""
    if device.monitor_type == 'ping':
        return collect_ping(device)
    if device.monitor_type == 'snmp':
        data = collect_snmp(device) or {}
        ping_data = collect_ping(device, samples=2)
        data.update(ping_data)
        return data or None
    if device.monitor_type == 'agent':
        data = collect_agent(device) or {}
        ping_data = collect_ping(device, samples=2)
        data.update(ping_data)
        return data or None
    return None
