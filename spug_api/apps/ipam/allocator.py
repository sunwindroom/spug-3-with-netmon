# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
自动化IP分配
------------
在网段内自动挑选下一个可用地址进行分配，最大限度减少手工录入；分配/释放/预留/更新
统一走同一入口写审计日志（IPChangeLog），从源头预防重复占用与人工录入出错。
"""
from django.db import transaction
from libs import human_datetime
from . import ipcalc
from .models import Subnet, IPAddress, IPChangeLog
import json


class IPAMError(Exception):
    pass


def _snapshot(ip_obj):
    if not ip_obj:
        return None
    return {
        'address': ip_obj.address, 'status': ip_obj.status, 'mac_address': ip_obj.mac_address,
        'hostname': ip_obj.hostname, 'owner': ip_obj.owner, 'device_id': ip_obj.device_id,
    }


def _log(subnet, address, action, before, after, operator, remark=None):
    IPChangeLog.objects.create(
        subnet=subnet, address=address, action=action,
        before=json.dumps(before) if before else None,
        after=json.dumps(after) if after else None,
        operator=operator, remark=remark
    )


def next_free_address(subnet):
    """按网段地址顺序找到第一个未被占用（无有效状态记录）的可用地址；网关地址默认跳过"""
    used = set(subnet.addresses.filter(status__in=IPAddress.USED_STATUSES).values_list('address', flat=True))
    for host in ipcalc.usable_hosts(subnet.cidr):
        addr = str(host)
        if addr == subnet.gateway or addr in used:
            continue
        return addr
    return None


@transaction.atomic
def allocate(subnet_id, operator, hostname=None, mac_address=None, device_id=None, owner=None,
             address=None, expires_at=None, desc=None):
    """自动分配（不传 address）或指定地址分配（传 address，会做重复占用校验）"""
    subnet = Subnet.objects.select_for_update().get(pk=subnet_id)

    if address:
        if not ipcalc.is_valid_ip_in_subnet(subnet.cidr, address):
            raise IPAMError(f'{address} 不属于网段 {subnet.cidr}')
        existing = IPAddress.objects.filter(subnet=subnet, address=address).first()
        if existing and existing.status in IPAddress.USED_STATUSES:
            raise IPAMError(f'{address} 已处于「{existing.get_status_display()}」状态，无法重复分配')
    else:
        address = next_free_address(subnet)
        if not address:
            raise IPAMError(f'网段 {subnet.cidr} 可用地址已耗尽，请扩容或清理长期未用地址')

    before = _snapshot(IPAddress.objects.filter(subnet=subnet, address=address).first())
    ip_obj, _ = IPAddress.objects.update_or_create(
        subnet=subnet, address=address,
        defaults=dict(
            status='allocated', hostname=hostname, mac_address=mac_address, device_id=device_id,
            owner=owner, allocated_at=human_datetime(), expires_at=expires_at, desc=desc,
            updated_at=human_datetime(),
        )
    )
    _log(subnet, address, 'allocate', before, _snapshot(ip_obj), operator)
    return ip_obj


@transaction.atomic
def reserve(subnet_id, address, operator, remark=None, desc=None):
    subnet = Subnet.objects.select_for_update().get(pk=subnet_id)
    if not ipcalc.is_valid_ip_in_subnet(subnet.cidr, address):
        raise IPAMError(f'{address} 不属于网段 {subnet.cidr}')
    existing = IPAddress.objects.filter(subnet=subnet, address=address).first()
    if existing and existing.status in IPAddress.USED_STATUSES:
        raise IPAMError(f'{address} 已处于「{existing.get_status_display()}」状态，无法预留')
    before = _snapshot(existing)
    ip_obj, _ = IPAddress.objects.update_or_create(
        subnet=subnet, address=address,
        defaults=dict(status='reserved', desc=desc, updated_at=human_datetime())
    )
    _log(subnet, address, 'reserve', before, _snapshot(ip_obj), operator, remark)
    return ip_obj


@transaction.atomic
def release(ip_id, operator, remark=None):
    ip_obj = IPAddress.objects.select_for_update().get(pk=ip_id)
    before = _snapshot(ip_obj)
    ip_obj.status = 'released'
    ip_obj.device_id = None
    ip_obj.updated_at = human_datetime()
    ip_obj.save(update_fields=['status', 'device_id', 'updated_at'])
    _log(ip_obj.subnet, ip_obj.address, 'release', before, _snapshot(ip_obj), operator, remark)
    return ip_obj


@transaction.atomic
def update_address(ip_id, operator, remark=None, **fields):
    ip_obj = IPAddress.objects.select_for_update().get(pk=ip_id)
    before = _snapshot(ip_obj)
    for k, v in fields.items():
        setattr(ip_obj, k, v)
    ip_obj.updated_at = human_datetime()
    ip_obj.save()
    _log(ip_obj.subnet, ip_obj.address, 'update', before, _snapshot(ip_obj), operator, remark)
    return ip_obj
