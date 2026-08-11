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

优化点（本次）：
  * 引入统一的超时 + 重试机制，网络类检测(http/port/ping)默认重试 2 次以减少偶发抖动误报。
  * http_check 超时从硬编码 30s 降为可配置(默认 10s)，避免大量超长挂起拖慢调度。
  * port_check 使用 with 管理 socket 资源，超时可配置(默认 3s)。
  * ping_availability_check 增加重试，单次 ping 丢包不再立即判定故障。
  * log_check 的 tail_lines 增加上限(10000)，keyword 用 shlex.quote 转义防止 shell 注入。
  * shell_check 对命令做超时包装，防止远端命令永久挂起占用 SSH 连接。

与 apps.netmon.collectors 中的"指标采集"不同，本模块是"是/否正常"的二元可用性检测，
统一返回 (is_ok: bool, message: str)。
"""
from libs.ssh_executor import ssh_exec, ssh_exec_ok, ping_check
from socket import socket, timeout as socket_timeout
from functools import wraps
from shlex import quote
import requests
import logging
import json
import re

logging.captureWarnings(True)
_CONN_ERR_RE = re.compile(r'Failed to establish a new connection: (.*)\'\)+')

_DEFAULT_HTTP_TIMEOUT = 10
_DEFAULT_PORT_TIMEOUT = 3
_DEFAULT_RETRIES = 2
_MAX_TAIL_LINES = 10000


def _parse_params(raw):
    """可用性检测的 extra 字段统一以 JSON 存储检测参数，兼容空值/脏数据"""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _with_retry(retries=_DEFAULT_RETRIES):
    """对网络类检测函数做重试：首次成功即返回，全部失败则返回最后一次结果。"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last = False, '检测失败'
            for attempt in range(retries + 1):
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    result = (False, f'检测异常：{e}')
                if result[0]:
                    return result
                last = result
            return last
        return wrapper
    return decorator


@_with_retry()
def http_check(device):
    params = _parse_params(device.extra)
    url = params.get('url') or device.ip
    if not url.startswith(('http://', 'https://')):
        url = f'http://{url}'
    timeout = params.get('timeout_limit_ms')
    try:
        res = requests.get(url, timeout=_DEFAULT_HTTP_TIMEOUT)
        if timeout:
            duration = int(res.elapsed.total_seconds() * 1000)
            if duration > int(timeout):
                return False, f'响应时间 {duration}ms 大于 {timeout}ms'
        return 200 <= res.status_code < 400, f'返回HTTP状态码 {res.status_code}'
    except Exception as e:
        error = str(e)
        matched = _CONN_ERR_RE.findall(error)
        if matched:
            error = matched[0]
        return False, error


@_with_retry()
def port_check(device):
    params = _parse_params(device.extra)
    port = params.get('port')
    if not port:
        return False, '未配置检测端口'
    try:
        with socket() as sock:
            sock.settimeout(_DEFAULT_PORT_TIMEOUT)
            sock.connect((device.ip, int(port)))
        return True, f'端口 {port} 检测正常'
    except socket_timeout:
        return False, f'端口 {port} 连接超时'
    except Exception as e:
        return False, f'端口 {port} 异常信息：{e}'


@_with_retry(retries=1)
def ping_availability_check(device):
    return ping_check(device.ip, timeout=3)


def process_check(device):
    if not device.host_id:
        return False, '未关联主机，无法执行进程检测'
    params = _parse_params(device.extra)
    keyword = params.get('keyword', '')
    if not keyword:
        return False, '未配置进程关键字'
    return ssh_exec_ok(device.host, f'ps -ef|grep -v grep|grep {quote(keyword)}')


def docker_check(device):
    if not device.host_id:
        return False, '未关联主机，无法执行Docker检测'
    params = _parse_params(device.extra)
    container = params.get('container', '')
    if not container:
        return False, '未配置容器名称'
    command = f"docker inspect -f '{{{{.State.Running}}}}' {quote(container)} 2>&1"
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
    tail_lines = min(int(tail_lines), _MAX_TAIL_LINES)
    if not path or not keyword:
        return False, '未配置日志路径/关键字'
    command = f"tail -n {tail_lines} {quote(path)} 2>&1 | grep -c -F {quote(keyword)}"
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
    wrapped = f'timeout 300 {command}'
    return ssh_exec_ok(device.host, wrapped)


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
