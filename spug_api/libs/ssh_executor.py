# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Released under the AGPL-3.0 License.
"""
公共 SSH / Ping 执行层
----------------------
将 apps.monitor.executors / apps.netmon.collectors / apps.netmon.remediation
中重复的 SSH 命令执行和 Ping 探测逻辑统一抽取到此模块，避免各模块各自维护
相同的 host.get_ssh() → ssh.exec_command_raw() 样板代码。
"""
import subprocess
import platform
import logging

logger = logging.getLogger(__name__)


def ssh_exec(host, command):
    """通过已纳管主机的 SSH 凭据执行命令，返回 (exit_code, stdout)。
    异常时返回 (非零, 错误信息) 而不抛出，便于调用方统一处理。

    用法:
        code, out = ssh_exec(host, 'df -h /')
        if code == 0: ...
    """
    try:
        with host.get_ssh() as ssh:
            exit_code, out = ssh.exec_command_raw(command)
        return exit_code, out or ''
    except Exception as e:
        logger.warning('SSH执行异常 host=%s: %s', host.hostname, e)
        return -1, f'异常信息：{e}'


def ssh_exec_ok(host, command):
    """ssh_exec 的便捷封装：执行成功返回 (True, stdout)，失败返回 (False, 错误信息)。"""
    exit_code, out = ssh_exec(host, command)
    if exit_code == 0:
        return True, out or '检测状态正常'
    return False, out or f'退出状态码：{exit_code}'


def ping_check(addr, timeout=3):
    """Ping 探测，返回 (成功, 消息)。
    timeout 单位为秒，在 Windows 上转换为毫秒参数。
    """
    try:
        system = platform.system().lower()
        if system == 'windows':
            cmd = f'ping -n 1 -w {int(timeout * 1000)} {addr}'
        else:
            cmd = f'ping -c 1 -W {int(timeout)} {addr}'
        task = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if task.returncode == 0:
            return True, 'Ping检测正常'
        return False, 'Ping检测失败'
    except Exception as e:
        return False, f'异常信息：{e}'