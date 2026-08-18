# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
自动发现
--------
输入一个 CIDR 网段，并发 Ping 扫描存活地址，再结合常见端口探测粗略判定设备类别，
供前端"自动发现"页面勾选后一键纳入资源台账（Device），免去逐台手工登记的繁琐流程。
"""
from django_redis import get_redis_connection
from concurrent.futures import ThreadPoolExecutor
from ipaddress import ip_network
from socket import socket, AF_INET, SOCK_STREAM
import subprocess
import platform
import socket as socket_mod
import json
import time

DISCOVERY_RESULT_KEY = 'spug:netmon:discovery:{}'
PORT_HINTS = (
    (161, 'switch'),  # SNMP 常见于网络设备
    (22, 'server'),
    (3389, 'server'),
    (443, 'application'),
    (80, 'application'),
    (3306, 'database'),
    (6379, 'database'),
)


def _is_alive(ip):
    system = platform.system().lower()
    cmd = f'ping -n 1 -w 800 {ip}' if system == 'windows' else f'ping -c 1 -W 1 {ip}'
    try:
        task = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return task.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def _probe_port(ip, port, timeout=0.6):
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except Exception:
        return False


def _guess_category(ip):
    open_ports = [p for p, _ in PORT_HINTS if _probe_port(ip, p)]
    for port, category in PORT_HINTS:
        if port in open_ports:
            return category, open_ports
    return 'other', open_ports


def _resolve_hostname(ip):
    try:
        return socket_mod.gethostbyaddr(ip)[0]
    except Exception:
        return ''


def _scan_one(ip):
    ip = str(ip)
    if not _is_alive(ip):
        return None
    category, open_ports = _guess_category(ip)
    return {
        'ip': ip,
        'hostname': _resolve_hostname(ip),
        'category_guess': category,
        'open_ports': open_ports,
    }


def scan_network(task_id, cidr, max_workers=64):
    """后台线程中执行：扫描完成后把结果写入 Redis，供前端轮询 /netmon/discovery 获取"""
    rds = get_redis_connection()
    key = DISCOVERY_RESULT_KEY.format(task_id)
    rds.set(key, json.dumps({'status': 'running', 'results': [], 'total': 0}), ex=1800)
    try:
        addresses = list(ip_network(cidr, strict=False).hosts())
    except ValueError as e:
        rds.set(key, json.dumps({'status': 'error', 'message': str(e), 'results': []}), ex=1800)
        return

    total = len(addresses)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for item in executor.map(_scan_one, addresses):
            if item:
                results.append(item)
            rds.set(key, json.dumps({
                'status': 'running', 'results': results, 'total': total, 'scanned': len(results)
            }), ex=1800)
    rds.set(key, json.dumps({
        'status': 'finished', 'results': results, 'total': total, 'finished_at': int(time.time())
    }), ex=1800)


def get_scan_result(task_id):
    rds = get_redis_connection()
    data = rds.get(DISCOVERY_RESULT_KEY.format(task_id))
    return json.loads(data) if data else {'status': 'not_found', 'results': []}
