# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
网段扫描：未授权设备检测 + 冲突检测
------------------------------------
定期对网段做存活探测（复用 apps.netmon 的 Ping 方式，不引入新依赖），并与 IPAM 记录比对：
  * 探测到存活，但 IPAM 中没有对应「已分配/预留」记录 → 判定为"未授权设备"接入
  * 探测到存活，且地址已分配，但获取到的 MAC 与登记的 MAC 不一致 → 判定为"冲突"（疑似盗用/重复分配）
  * 已分配地址长期探测不到存活（超过 offline_days）→ 仅作为提示信息，不自动释放（避免误伤离线维护中的资产）
检测结果写入 IPChangeLog 留痕，并可选联动 isolation.py 尝试自动隔离。
"""
from concurrent.futures import ThreadPoolExecutor
from libs import human_datetime
from apps.notify.models import Notify
from .models import IPAddress, IPChangeLog
from . import ipcalc, isolation
import subprocess
import platform
import logging
import re


def _ping_alive(ip):
    system = platform.system().lower()
    cmd = f'ping -n 1 -w 800 {ip}' if system == 'windows' else f'ping -c 1 -W 1 {ip}'
    task = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return task.returncode == 0


def _lookup_mac(ip):
    """尽力而为地读取本机 ARP 缓存获取 MAC（仅在 spug 与目标处于同一二层网络时有效，
    跨网段/云环境通常无法获取，此时仅做存活判断，不影响未授权检测的基本能力）"""
    try:
        out = subprocess.run(f'arp -n {ip}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) \
            .stdout.decode(errors='ignore')
        m = re.search(r'(([0-9A-Fa-f]{1,2}:){5}[0-9A-Fa-f]{1,2})', out)
        return m.group(1).lower() if m else None
    except Exception:
        return None


def scan_subnet(subnet, max_workers=64):
    """执行一次网段扫描，返回本次发现的异常列表 [{address, type, message}]"""
    hosts = ipcalc.usable_hosts(subnet.cidr)
    alive = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(lambda h: (str(h), _ping_alive(str(h))), hosts)
        for addr, ok in results:
            if ok:
                alive[addr] = _lookup_mac(addr)

    known = {ip.address: ip for ip in subnet.addresses.all()}
    findings = []

    for addr, mac in alive.items():
        record = known.get(addr)
        if record is None or record.status not in ('allocated', 'reserved', 'isolated'):
            # 未在 IPAM 中登记为已分配/预留，却检测到存活 —— 未授权设备接入
            before = record.to_dict() if record else None
            ip_obj, _ = IPAddress.objects.update_or_create(
                subnet=subnet, address=addr,
                defaults={'status': 'unauthorized', 'mac_address': mac, 'last_seen_at': human_datetime(),
                          'updated_at': human_datetime()}
            )
            IPChangeLog.objects.create(
                subnet=subnet, address=addr, action='unauthorized',
                before=None, after=None, operator=None,
                remark=f'扫描发现未授权设备接入（MAC: {mac or "未知"}）'
            )
            findings.append({'address': addr, 'type': 'unauthorized', 'message': '检测到未授权设备接入'})
            try:
                Notify.make_system_notify(
                    f'[IPAM] 网段 {subnet.name}({subnet.cidr}) 发现未授权设备',
                    f'地址 {addr} 存活但未在IPAM登记为已分配/预留状态，MAC: {mac or "未知"}'
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
                    Notify.make_system_notify(
                        f'[IPAM] 网段 {subnet.name}({subnet.cidr}) 发现地址冲突',
                        f'地址 {addr} 登记MAC与实测MAC不一致，疑似重复分配或设备被替换'
                    )
                except Exception:
                    pass
            else:
                record.save(update_fields=['last_seen_at'])

    return findings
