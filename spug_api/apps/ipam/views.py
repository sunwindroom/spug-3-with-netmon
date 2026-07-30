# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
from django.views.generic import View
from libs import json_response, JsonParser, Argument, auth
from apps.ipam.models import Subnet, IPAddress, IPChangeLog, IsolationTemplate
from apps.ipam import allocator, predictor, scanner, isolation, ipcalc
from apps.netmon.models import Device, NetGroup
from apps.host.models import Host
from threading import Thread
import uuid
import json


# ------------------------------------------------------------------ 网段管理 -----
class SubnetView(View):
    @auth('ipam.subnet.view')
    def get(self, request):
        return json_response([x.to_view() for x in Subnet.objects.all()])

    @auth('ipam.subnet.add|ipam.subnet.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入网段名称'),
            Argument('cidr', help='请输入CIDR，例如 192.168.1.0/24'),
            Argument('group_id', type=int, required=False),
            Argument('vlan_id', type=int, required=False),
            Argument('gateway', required=False),
            Argument('dns_servers', required=False),
            Argument('warning_threshold', type=int, default=80),
            Argument('auto_isolate_unauthorized', type=bool, default=False),
            Argument('desc', required=False),
        ).parse(request.body)
        if error:
            return json_response(error=error)
        try:
            ipcalc.parse_network(form.cidr)
        except ValueError:
            return json_response(error=f'{form.cidr} 不是合法的CIDR')
        subnet_id = form.pop('id', None)
        if subnet_id:
            Subnet.objects.filter(pk=subnet_id).update(**form)
        else:
            Subnet.objects.create(created_by=request.user, **form)
        return json_response()

    @auth('ipam.subnet.del')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            Subnet.objects.filter(pk=form.id).delete()
        return json_response(error=error)


@auth('ipam.subnet.view')
def get_subnet_addresses(request, subnet_id):
    """返回网段内全部地址（已登记状态的地址来自数据库，其余按网段范围隐式补全为"空闲"）"""
    subnet = Subnet.objects.filter(pk=subnet_id).first()
    if not subnet:
        return json_response(error='网段不存在')
    hosts = ipcalc.usable_hosts(subnet.cidr)
    if len(hosts) > ipcalc.MAX_MATERIALIZE:
        return json_response(error=f'网段过大（{len(hosts)}个地址），暂不支持全量展开，请缩小网段范围或直接搜索地址')
    known = {ip.address: ip.to_view() for ip in subnet.addresses.all()}
    result = []
    for host in hosts:
        addr = str(host)
        if addr in known:
            result.append(known[addr])
        else:
            result.append({'address': addr, 'status': 'free', 'status_alias': '空闲'})
    return json_response(result)


# ------------------------------------------------------------------ 地址分配 -----
@auth('ipam.address.add')
def allocate_address(request):
    form, error = JsonParser(
        Argument('subnet_id', type=int, help='请选择网段'),
        Argument('address', required=False, help='留空表示自动分配下一个可用地址'),
        Argument('hostname', required=False),
        Argument('mac_address', required=False),
        Argument('device_id', type=int, required=False),
        Argument('owner', required=False),
        Argument('expires_at', required=False),
        Argument('desc', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    try:
        ip_obj = allocator.allocate(
            form.subnet_id, request.user, hostname=form.hostname, mac_address=form.mac_address,
            device_id=form.device_id, owner=form.owner, address=form.address,
            expires_at=form.expires_at, desc=form.desc
        )
    except allocator.IPAMError as e:
        return json_response(error=str(e))
    return json_response(ip_obj.to_view())


@auth('ipam.address.edit')
def reserve_address(request):
    form, error = JsonParser(
        Argument('subnet_id', type=int, help='请选择网段'),
        Argument('address', help='请输入要预留的地址'),
        Argument('desc', required=False),
        Argument('remark', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    try:
        ip_obj = allocator.reserve(form.subnet_id, form.address, request.user, remark=form.remark, desc=form.desc)
    except allocator.IPAMError as e:
        return json_response(error=str(e))
    return json_response(ip_obj.to_view())


@auth('ipam.address.edit')
def release_address(request):
    form, error = JsonParser(
        Argument('id', type=int, help='请指定地址记录'),
        Argument('remark', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    ip_obj = allocator.release(form.id, request.user, remark=form.remark)
    return json_response(ip_obj.to_view())


@auth('ipam.address.edit')
def update_address(request):
    form, error = JsonParser(
        Argument('id', type=int, help='请指定地址记录'),
        Argument('hostname', required=False),
        Argument('mac_address', required=False),
        Argument('owner', required=False),
        Argument('device_id', type=int, required=False),
        Argument('expires_at', required=False),
        Argument('desc', required=False),
        Argument('remark', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    ip_id = form.pop('id')
    remark = form.pop('remark', None)
    ip_obj = allocator.update_address(ip_id, request.user, remark=remark, **form)
    return json_response(ip_obj.to_view())


@auth('ipam.address.edit')
def isolate_address(request):
    form, error = JsonParser(
        Argument('id', type=int, help='请指定地址记录'),
        Argument('remark', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    ip_obj = isolation.isolate(form.id, request.user, remark=form.remark)
    return json_response(ip_obj.to_view())


@auth('ipam.address.edit')
def restore_address(request):
    form, error = JsonParser(
        Argument('id', type=int, help='请指定地址记录'),
        Argument('remark', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    ip_obj = isolation.restore(form.id, request.user, remark=form.remark)
    return json_response(ip_obj.to_view())


# ------------------------------------------------------------------ 未授权/冲突列表 -----
@auth('ipam.subnet.view')
def get_security_events(request):
    qs = IPAddress.objects.filter(status__in=['unauthorized', 'conflict', 'isolated']).select_related('subnet')
    return json_response([x.to_view() for x in qs])


# ------------------------------------------------------------------ 网段扫描 -----
@auth('ipam.subnet.edit')
def start_scan(request):
    form, error = JsonParser(Argument('subnet_id', type=int, help='请选择网段')).parse(request.body)
    if error:
        return json_response(error=error)
    subnet = Subnet.objects.filter(pk=form.subnet_id).first()
    if not subnet:
        return json_response(error='网段不存在')
    try:
        scan_results, findings = scanner.scan_subnet(subnet)
    except Exception as e:
        return json_response(error=f'扫描失败: {str(e)}')
    return json_response({'scan_results': scan_results, 'findings': findings})


# ------------------------------------------------------------------ 导入发现设备 -----
@auth('ipam.subnet.edit')
def import_discovery(request):
    form, error = JsonParser(
        Argument('subnet_id', type=int, help='请选择网段'),
        Argument('devices', type=list, help='请选择要导入的设备'),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    subnet = Subnet.objects.filter(pk=form.subnet_id).first()
    if not subnet:
        return json_response(error='网段不存在')
    imported = []
    for item in form.devices:
        address = item.get('address')
        if not address:
            continue
        category = item.get('category_guess', 'other')
        hostname = item.get('hostname') or address
        host_obj = Host.objects.filter(hostname=hostname).first()
        if not host_obj:
            host_obj = Host.objects.create(
                hostname=hostname,
                type='linux' if category in ('server', 'database', 'application') else 'switch',
                desc=f'由IPAM扫描自动导入，网段: {subnet.name}',
            )
        group_id = item.get('group_id')
        if group_id:
            group = NetGroup.objects.filter(pk=group_id).first()
        else:
            group = NetGroup.objects.filter(name='默认分组').first()
        if not group:
            group = NetGroup.objects.create(name='默认分组')
        device_obj = Device.objects.filter(host_id=host_obj.id).first()
        if not device_obj:
            device_obj = Device.objects.create(
                name=hostname,
                host_id=host_obj.id,
                group_id=group.id,
                category=category,
            )
        ip_obj = IPAddress.objects.filter(subnet=subnet, address=address).first()
        if ip_obj:
            IPAddress.objects.filter(pk=ip_obj.id).update(
                status='allocated', device_id=device_obj.id, hostname=hostname,
                mac_address=item.get('mac') or ip_obj.mac_address,
            )
        else:
            IPAddress.objects.create(
                subnet=subnet, address=address, status='allocated',
                device_id=device_obj.id, hostname=hostname,
                mac_address=item.get('mac'),
            )
        imported.append({'address': address, 'hostname': hostname, 'device_id': device_obj.id})
    return json_response({'imported': imported, 'count': len(imported)})


# ------------------------------------------------------------------ 预测性洞察 -----
@auth('ipam.subnet.view')
def get_insights(request):
    subnet_id = request.GET.get('subnet_id')
    if subnet_id:
        subnet = Subnet.objects.filter(pk=subnet_id).first()
        if not subnet:
            return json_response(error='网段不存在')
        return json_response(predictor.forecast_subnet(subnet))
    return json_response(predictor.forecast_all())


# ------------------------------------------------------------------ 变更审计 -----
@auth('ipam.subnet.view')
def get_change_logs(request):
    qs = IPChangeLog.objects.all()
    subnet_id = request.GET.get('subnet_id')
    address = request.GET.get('address')
    action = request.GET.get('action')
    start = request.GET.get('start')
    end = request.GET.get('end')
    if subnet_id:
        qs = qs.filter(subnet_id=subnet_id)
    if address:
        qs = qs.filter(address__icontains=address)
    if action:
        qs = qs.filter(action=action)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    return json_response([x.to_view() for x in qs[:1000]])


# ------------------------------------------------------------------ 隔离模板 -----
class IsolationTemplateView(View):
    @auth('ipam.subnet.view')
    def get(self, request):
        return json_response([x.to_view() for x in IsolationTemplate.objects.all()])

    @auth('ipam.subnet.edit')
    def post(self, request):
        form, error = JsonParser(
            Argument('id', type=int, required=False),
            Argument('name', help='请输入模板名称'),
            Argument('device_id', type=int, help='请选择执行隔离脚本的网络设备'),
            Argument('isolate_script', help='请输入隔离脚本'),
            Argument('restore_script', required=False),
            Argument('is_default', type=bool, default=False),
        ).parse(request.body)
        if error:
            return json_response(error=error)
        tpl_id = form.pop('id', None)
        if form.is_default:
            IsolationTemplate.objects.update(is_default=False)
        if tpl_id:
            IsolationTemplate.objects.filter(pk=tpl_id).update(**form)
        else:
            IsolationTemplate.objects.create(created_by=request.user, **form)
        return json_response()

    @auth('ipam.subnet.del')
    def delete(self, request):
        form, error = JsonParser(Argument('id', type=int, help='请指定操作对象')).parse(request.GET)
        if error is None:
            IsolationTemplate.objects.filter(pk=form.id).delete()
        return json_response(error=error)
