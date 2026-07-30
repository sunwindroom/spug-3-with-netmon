# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
网段扫描：并发Ping探测存活主机 + 常见端口扫描 + 设备类型推断
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from libs import human_datetime
from .models import IPAddress, IPChangeLog
from . import ipcalc, isolation
import subprocess
import platform
import socket
import logging

PORT_HINTS = {
    22: 'server', 161: 'switch', 3389: 'server', 443: 'application',
    80: 'application', 3306: 'database', 6379: 'database', 5432: 'database',
    27017: 'database', 8080: 'application', 8443: 'application',
    23: 'router', 830: 'switch', 179: 'router', 514: 'firewall',
    4433: 'load_balancer', 5000: 'storage', 5022: 'storage',
}

COMMON_PORTS = [22, 23, 80, 161, 443, 830, 179, 3389, 3306, 5432, 6379, 8080, 8443, 27017, 514, 4433, 5000, 5022]


def _ping_alive(ip):
    system = platform.system().lower()
    cmd = f'ping -n 1 -w 800 {ip}' if system == 'windows' else f'ping -c 1 -W 1 {ip}'
    task = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return task.returncode == 0


def _scan_ports(ip, timeout=1.0):
    open_ports = []
    for port in COMMON_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            result = s.connect_ex((ip, port))
            if result == 0:
                open_ports.append(port)
            s.close()
        except Exception:
            pass
    return open_ports


def _guess_category(open_ports):
    if not open_ports:
        return 'other'
    scores = {}
    for port in open_ports:
        cat = PORT_HINTS.get(port)
        if cat:
            scores[cat] = scores.get(cat, 0) + 1
    if not scores:
        return 'other'
    return max(scores, key=scores.get)


def _lookup_mac(ip):
    import re
    try:
        out = subprocess.run(f'arp -n {ip}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) \
            .stdout.decode(errors='ignore')
        m = re.search(r'(([0-9A-Fa-f]{1,2}:){5}[0-9A-Fa-f]{1,2})', out)
        return m.group(1).lower() if m else None
    except Exception:
        return None


def scan_subnet(subnet, max_workers=64):
    hosts = ipcalc.usable_hosts(subnet.cidr)
    alive = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(lambda h: (str(h), _ping_alive(str(h))), h): h for h in hosts}
        for future in as_completed(futures):
            try:
                addr, ok = future.result()
                if ok:
                    alive[addr] = True
            except Exception:
                pass

    scan_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        port_futures = {executor.submit(_scan_ports, addr): addr for addr in alive}
        for future in as_completed(port_futures):
            addr = port_futures[future]
            try:
                open_ports = future.result()
            except Exception:
                open_ports = []
            mac = _lookup_mac(addr)
            category = _guess_category(open_ports)
            scan_results.append({
                'address': addr, 'alive': True, 'mac': mac,
                'open_ports': open_ports, 'category_guess': category,
            })

    known = {ip.address: ip for ip in subnet.addresses.all()}
    findings = []

    for item in scan_results:
        addr = item['address']
        mac = item['mac']
        record = known.get(addr)
        if record is None or record.status not in ('allocated', 'reserved', 'isolated'):
            before = record.to_dict() if record else None
            ip_obj, _ = IPAddress.objects.update_or_create(
                subnet=subnet, address=addr,
                defaults={'status': 'unauthorized', 'mac_address': mac, 'last_seen_at': human_datetime(),
                          'updated_at': human_datetime()}
            )
            IPChangeLog.objects.create(
                subnet=subnet, address=addr, action='unauthorized',
                before=None, after=None, operator=None,
                remark=f'扫描发现未授权设备接入（MAC: {mac or "未知"}, 开放端口: {item["open_ports"] or "无"}）'
            )
            findings.append({'address': addr, 'type': 'unauthorized', 'message': '检测到未授权设备接入'})
            try:
                from apps.notify.models import Notify
                Notify.make_system_notify(
                    f'[IPAM] 网段 {subnet.name}({subnet.cidr}) 发现未授权设备',
                    f'地址 {addr} 存活但未在IPAM登记，MAC: {mac or "未知"}, 开放端口: {item["open_ports"]}'
                )
            except Exception as e:
                logging.warning(f'未授权设备通知发送失败: {e}')
            if subnet.auto_isolate_unauthorized:
                isolation.isolate(ip_obj.id, operator=None, remark='未授权设备自动隔离', auto=True)
        else:
            record.last_seen_at = human_datetime()
            if mac and record.mac_address and mac != record.mac_address.lower():
                record.status = 'conflict'
                record.save(update_fields=['status', 'last_seen_at'])
                IPChangeLog.objects.create(
                    subnet=subnet, address=addr, action='conflict',
                    before=None, after=None, operator=None,
                    remark=f'MAC 不一致：登记值 {record.mac_address}，实测值 {mac}'
                )
                findings.append({'address': addr, 'type': 'conflict', 'message': f'MAC不一致（登记{record.mac_address} / 实测{mac}）'})
                try:
                    from apps.notify.models import Notify
                    Notify.make_system_notify(
                        f'[IPAM] 网段 {subnet.name}({subnet.cidr}) 发现地址冲突',
                        f'地址 {addr} 登记MAC与实测MAC不一致，疑似重复分配或设备被替换'
                    )
                except Exception:
                    pass
            else:
                record.save(update_fields=['last_seen_at'])

    return scan_results, findings
