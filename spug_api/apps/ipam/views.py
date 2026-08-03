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
    existing_hosts = {h.hostname for h in Host.objects.all()}
    for item in scan_results:
        item['registered'] = item['address'] in existing_hosts
    return json_response({'scan_results': scan_results, 'findings': findings})


# ------------------------------------------------------------------ 测试连接 -----
@auth('ipam.subnet.edit')
def test_connection(request):
    from apps.setting.utils import AppSetting
    from libs.ssh import SSH, AuthenticationException
    from paramiko.ssh_exception import BadAuthenticationType
    import socket as _socket
    form, error = JsonParser(
        Argument('hostname', help='请输入主机名或IP'),
        Argument('port', type=int, default=22),
        Argument('username', default='root'),
        Argument('password', required=False),
        Argument('pkey', required=False),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    try:
        if form.pkey:
            with SSH(form.hostname, form.port, form.username, form.pkey) as ssh:
                ssh.ping()
            return json_response({'ok': True, 'message': '密钥认证成功'})
        private_key, _ = AppSetting.get_ssh_key()
        if form.password:
            try:
                with SSH(form.hostname, form.port, form.username, password=form.password) as ssh:
                    ssh.ping()
                return json_response({'ok': True, 'message': '密码认证成功'})
            except AuthenticationException:
                pass
        with SSH(form.hostname, form.port, form.username, private_key) as ssh:
            ssh.ping()
        return json_response({'ok': True, 'message': '全局密钥认证成功'})
    except BadAuthenticationType:
        return json_response({'ok': False, 'message': '不支持的认证方式'})
    except AuthenticationException:
        return json_response({'ok': False, 'message': '认证失败，请检查密码或密钥'})
    except _socket.timeout:
        return json_response({'ok': False, 'message': '连接超时，请检查网络'})
    except Exception as e:
        return json_response({'ok': False, 'message': f'连接失败: {str(e)}'})


# ------------------------------------------------------------------ 导入发现设备 -----
@auth('ipam.subnet.edit')
def import_discovery(request):
    from apps.host.models import Group as HostGroup
    from apps.account.models import User
    form, error = JsonParser(
        Argument('subnet_id', type=int, help='请选择网段'),
        Argument('devices', type=list, help='请选择要导入的设备'),
    ).parse(request.body)
    if error:
        return json_response(error=error)
    subnet = Subnet.objects.filter(pk=form.subnet_id).first()
    if not subnet:
        return json_response(error='网段不存在')
    current_user_id = None
    try:
        current_user_id = request.user.pk
    except Exception:
        pass
    if not current_user_id:
        try:
            access_token = request.headers.get('x-token') or request.GET.get('x-token')
            if access_token:
                current_user_id = User.objects.filter(access_token=access_token, is_active=True).values_list('id', flat=True).first()
        except Exception:
            pass
    if not current_user_id:
        current_user_id = User.objects.filter(is_supper=True).values_list('id', flat=True).first()
    imported = []
    errors = []
    for item in form.devices:
        address = item.get('address')
        if not address:
            continue
        category = item.get('category_guess', 'other')
        host_name = item.get('host_name') or address
        host_hostname = item.get('host_hostname') or address
        host_port = item.get('host_port') or 22
        host_username = item.get('host_username') or 'root'
        host_pkey = item.get('host_pkey') or ''
        host_password = item.get('host_password') or ''
        host_group_id = item.get('host_group_id')
        existing = Host.objects.filter(hostname=host_hostname, port=host_port).first()
        if existing:
            errors.append(f'{address}: 主机已存在（{existing.name}），跳过')
            continue
        host_obj = Host.objects.create(
            name=host_name,
            hostname=host_hostname,
            port=host_port,
            username=host_username,
            pkey=host_pkey if host_pkey else None,
            desc=f'由IPAM扫描导入，网段: {subnet.name}',
            created_by_id=current_user_id,
            is_verified=False,
        )
        if host_password:
            try:
                from apps.setting.utils import AppSetting
                from libs.ssh import SSH
                _, public_key = AppSetting.get_ssh_key()
                with SSH(host_hostname, host_port, host_username, password=host_password) as ssh:
                    ssh.add_public_key(public_key)
                Host.objects.filter(pk=host_obj.id).update(is_verified=True)
            except Exception:
                pass
        if host_group_id:
            hg = HostGroup.objects.filter(pk=host_group_id).first()
            if hg:
                hg.hosts.add(host_obj)
        else:
            default_grp = HostGroup.objects.first()
            if default_grp:
                default_grp.hosts.add(host_obj)
        net_group = NetGroup.objects.filter(name='默认分组').first()
        if not net_group:
            net_group = NetGroup.objects.create(name='默认分组')
        device_obj = Device.objects.filter(host_id=host_obj.id).first()
        if not device_obj:
            device_obj = Device.objects.create(
                name=host_name,
                ip=address,
                host_id=host_obj.id,
                group_id=net_group.id,
                category=category,
                created_by_id=current_user_id,
            )
        ip_obj = IPAddress.objects.filter(subnet=subnet, address=address).first()
        if ip_obj:
            IPAddress.objects.filter(pk=ip_obj.id).update(
                status='allocated', device_id=device_obj.id, hostname=host_name,
                mac_address=item.get('mac') or ip_obj.mac_address,
            )
        else:
            IPAddress.objects.create(
                subnet=subnet, address=address, status='allocated',
                device_id=device_obj.id, hostname=host_name,
                mac_address=item.get('mac'),
            )
        imported.append({'address': address, 'host_name': host_name, 'host_id': host_obj.id, 'device_id': device_obj.id})
    return json_response({'imported': imported, 'count': len(imported), 'errors': errors})


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
