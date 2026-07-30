# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
未授权设备隔离协助
------------------
"隔离"在不同网络环境中的落地方式差异很大（交换机端口关闭、防火墙ACL、NAC联动等），
本模块不假设对接任何特定厂商设备，而是提供一个通用协助入口：
  1. 始终先将地址标记为 isolated 并写入审计日志，供人工在网管系统上确认处置
  2. 如果配置了 IsolationTemplate（绑定一台可 SSH 登录的网关/防火墙/交换机设备），
     则自动执行其中的隔离脚本（脚本内容由管理员自行编写，适配自己的设备型号/厂商命令）
未绑定模板时不会假装执行了真实的网络隔离，只会提示"需人工处置"，避免造成误导。
"""
from libs import human_datetime
from apps.notify.models import Notify
from .models import IPAddress, IPChangeLog, IsolationTemplate
import logging


def _run_script(device, script, address):
    try:
        with device.host.get_ssh() as ssh:
            exit_code, out = ssh.exec_command_raw(script.format(ip=address))
        return exit_code == 0, out or ''
    except Exception as e:
        return False, f'执行异常: {e}'


def isolate(ip_id, operator, remark=None, auto=False):
    ip_obj = IPAddress.objects.select_related('subnet').get(pk=ip_id)
    before = {'status': ip_obj.status}
    ip_obj.status = 'isolated'
    ip_obj.updated_at = human_datetime()
    ip_obj.save(update_fields=['status', 'updated_at'])

    template = IsolationTemplate.objects.filter(is_default=True).first()
    executed_note = '未配置默认隔离模板，请人工在网络设备上完成隔离处置'
    if template and template.device.host_id:
        success, output = _run_script(template.device, template.isolate_script, ip_obj.address)
        executed_note = f'已自动执行隔离脚本（{template.name}），结果：{"成功" if success else "失败"}；输出：{output[:300]}'

    IPChangeLog.objects.create(
        subnet=ip_obj.subnet, address=ip_obj.address, action='isolate',
        before=None, after=None, operator=operator,
        remark=f'{remark or ""}；{executed_note}'
    )
    try:
        Notify.make_system_notify(
            f'[IPAM] 地址 {ip_obj.address} 已{"自动" if auto else ""}隔离',
            executed_note
        )
    except Exception as e:
        logging.warning(f'隔离结果通知发送失败: {e}')
    return ip_obj


def restore(ip_id, operator, remark=None):
    ip_obj = IPAddress.objects.select_related('subnet').get(pk=ip_id)
    ip_obj.status = 'allocated'
    ip_obj.updated_at = human_datetime()
    ip_obj.save(update_fields=['status', 'updated_at'])

    template = IsolationTemplate.objects.filter(is_default=True).first()
    executed_note = ''
    if template and template.restore_script and template.device.host_id:
        success, output = _run_script(template.device, template.restore_script, ip_obj.address)
        executed_note = f'已自动执行解除隔离脚本，结果：{"成功" if success else "失败"}；输出：{output[:300]}'

    IPChangeLog.objects.create(
        subnet=ip_obj.subnet, address=ip_obj.address, action='restore',
        before=None, after=None, operator=operator, remark=f'{remark or ""}；{executed_note}'
    )
    return ip_obj
