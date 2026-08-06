# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
可用性检测（CHECK_TYPES）
------------------------
本模块合并自原 apps.monitor.executors，是本次"监控中心(monitor) + IT资源监控(netmon)"
模块统一后的唯一实现，修复了原实现中的问题：
  * 原 monitor/executors.py 的 docker_check()/log_check() 调用了未导入的 ssh_exec，
    只要用户配置 Docker检测/日志监控就会直接 NameError 报错，本次已修复。
  * 原 netmon 的 MONITOR_TYPES 中声明了 'http' 选项，但采集分发从未实现该分支，
    选择该类型后设备状态永远不会更新，本次已补齐实现。

与 apps.netmon.collectors 中的"指标采集"不同，本模块是"是/否正常"的二元可用性检测，
统一返回 (is_ok: bool, message: str)。
"""
from libs.ssh_executor import ssh_exec, ssh_exec_ok, ping_check
from socket import socket
import requests
import logging
import json
import re

logging.captureWarnings(True)
_CONN_ERR_RE = re.compile(r'Failed to establish a new connection: (.*)\'\)+')


def _parse_params(raw):
    """可用性检测的 extra 字段统一以 JSON 存储检测参数，兼容空值/脏数据"""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def http_check(device):
    params = _parse_params(device.extra)
    url = params.get('url') or device.ip
    limit = params.get('timeout_limit_ms')
    try:
        res = requests.get(url, timeout=30)
        if limit:
            duration = int(res.elapsed.total_seconds() * 1000)
            if duration > int(limit):
                return False, f'响应时间 {duration}ms 大于 {limit}ms'
        return 200 <= res.status_code < 400, f'返回HTTP状态码 {res.status_code}'
    except Exception as e:
        error = str(e)
        matched = _CONN_ERR_RE.findall(error)
        if matched:
            error = matched[0]
        return False, error


def port_check(device):
    params = _parse_params(device.extra)
    port = params.get('port')
    if not port:
        return False, '未配置检测端口'
    try:
        sock = socket()
        sock.settimeout(5)
        sock.connect((device.ip, int(port)))
        sock.close()
        return True, f'端口 {port} 检测正常'
    except Exception as e:
        return False, f'端口 {port} 异常信息：{e}'


def ping_availability_check(device):
    return ping_check(device.ip, timeout=3)


def process_check(device):
    if not device.host_id:
        return False, '未关联主机，无法执行进程检测'
    params = _parse_params(device.extra)
    keyword = params.get('keyword', '')
    if not keyword:
        return False, '未配置进程关键字'
    return ssh_exec_ok(device.host, f'ps -ef|grep -v grep|grep {keyword!r}')


def docker_check(device):
    if not device.host_id:
        return False, '未关联主机，无法执行Docker检测'
    params = _parse_params(device.extra)
    container = params.get('container', '')
    if not container:
        return False, '未配置容器名称'
    command = f"docker inspect -f '{{{{.State.Running}}}}' {container!r} 2>&1"
    exit_code, out = ssh_exec(device.host, command)
    out = (out or '').strip()
    if exit_code == 0 and out == 'true':
        return True, f'容器 {container} 运行中'
    if 'No such object' in out:
        return False, f'容器 {container} 不存在'
    return False, f'容器 {container} 未运行，状态：{out}'


def log_check(device):
    if not device.host_id:
        return False, '未关联主机，无法执行日志检测'
    params = _parse_params(device.extra)
    path, keyword = params.get('path', ''), params.get('keyword', '')
    tail_lines = params.get('tail_lines') or 200
    if not path or not keyword:
        return False, '未配置日志路径/关键字'
    command = f"tail -n {int(tail_lines)} {path} 2>&1 | grep -c -F {keyword!r}"
    exit_code, out = ssh_exec(device.host, command)
    out = (out or '0').strip()
    count = int(out) if out.isdigit() else 0
    if count > 0:
        return False, f'日志 {path} 最近{tail_lines}行中发现 {count} 处关键字「{keyword}」'
    return True, f'日志 {path} 最近{tail_lines}行未发现关键字「{keyword}」'


def shell_check(device):
    if not device.host_id:
        return False, '未关联主机，无法执行命令检测'
    command = device.extra or ''
    if not command:
        return False, '未配置检测脚本'
    return ssh_exec_ok(device.host, command)


CHECK_FUNCS = {
    'http': http_check,
    'port': port_check,
    'database': port_check,
    'ping_check': ping_availability_check,
    'process': process_check,
    'docker': docker_check,
    'log': log_check,
    'shell': shell_check,
}


def run_check(device):
    """统一入口：根据设备的可用性检测类型分发，返回 (is_ok, message)"""
    func = CHECK_FUNCS.get(device.monitor_type)
    if not func:
        raise TypeError(f'invalid check type: {device.monitor_type!r}')
    return func(device)
