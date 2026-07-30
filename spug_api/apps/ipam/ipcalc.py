# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
"""
网段地址计算工具。为避免对超大网段（如 /16）逐个物化 IPAddress 记录导致的存储/性能问题，
"空闲(free)"地址被设计为隐式状态：数据库里只保存"已被分配/预留/冲突/未授权/隔离"等
有意义状态的地址记录；空闲地址 = 网段可用主机地址集合 - 已有记录地址集合，按需实时计算。
"""
from ipaddress import ip_network, ip_address


def parse_network(cidr):
    return ip_network(cidr, strict=False)


def usable_hosts(cidr):
    """返回网段内可分配的主机地址迭代器（排除网络地址/广播地址；/31、/32 特殊网段全量可用）"""
    net = parse_network(cidr)
    if net.num_addresses <= 2:
        return list(net)
    return list(net.hosts())


def total_usable(cidr):
    net = parse_network(cidr)
    return net.num_addresses if net.num_addresses <= 2 else net.num_addresses - 2


def is_valid_ip_in_subnet(cidr, addr):
    try:
        return ip_address(addr) in parse_network(cidr)
    except ValueError:
        return False


MAX_MATERIALIZE = 65536  # 前端"全量地址视图"允许展开的网段上限（如 /16），超出建议分页/仅查看已用地址
