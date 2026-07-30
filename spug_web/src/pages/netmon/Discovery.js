/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useState } from 'react';
import { observer } from 'mobx-react';
import { Card, Input, Button, Table, Space, Select, Progress, message, Tag, Alert } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import store from './store';

const CATEGORY_LABEL = {
  server: '服务器', switch: '交换机', router: '路由器', firewall: '防火墙',
  load_balancer: '负载均衡', storage: '存储设备', database: '数据库',
  middleware: '中间件', application: '业务应用', other: '其他',
};

export default observer(function Discovery() {
  const [cidr, setCidr] = useState('192.168.1.0/24');
  const [selected, setSelected] = useState([]);
  const [groupId, setGroupId] = useState(undefined);
  const [scanning, setScanning] = useState(false);
  const [importing, setImporting] = useState(false);

  function handleScan() {
    setScanning(true);
    setSelected([]);
    store.startDiscovery(cidr).finally(() => setScanning(false));
  }

  function handleImport() {
    if (!selected.length) return message.warning('请先勾选要导入的设备');
    setImporting(true);
    store.importDiscovery(selected, groupId)
      .then(({ created }) => message.success(`已导入 ${created} 台设备，可前往「资源台账」查看`))
      .finally(() => setImporting(false))
  }

  const result = store.discoveryResult;
  const running = result.status === 'running';
  const percent = result.total ? Math.round(((result.scanned || 0) / result.total) * 100) : 0;

  const columns = [
    { title: 'IP地址', dataIndex: 'ip' },
    { title: '主机名', dataIndex: 'hostname', render: v => v || '-' },
    { title: '推测类型', dataIndex: 'category_guess', render: v => <Tag>{CATEGORY_LABEL[v] || v}</Tag> },
    { title: '开放端口', dataIndex: 'open_ports', render: v => (v || []).join(', ') || '-' },
  ];

  return (
    <Card title="网段自动发现">
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="输入待扫描的网段（CIDR），系统将并发 Ping 探测存活主机并结合常见端口粗略判断设备类型，扫描完成后可勾选批量导入到资源台账。"
      />
      <Space style={{ marginBottom: 16 }}>
        <Input
          style={{ width: 260 }} value={cidr} onChange={e => setCidr(e.target.value)}
          placeholder="例如：192.168.1.0/24"
        />
        <Button type="primary" icon={<SearchOutlined/>} loading={scanning || running} onClick={handleScan}>
          开始扫描
        </Button>
      </Space>

      {(running || result.status === 'finished') &&
        <Progress percent={running ? percent : 100} status={running ? 'active' : 'success'} style={{ marginBottom: 16 }}/>}

      <Space style={{ marginBottom: 12 }}>
        <Select allowClear style={{ width: 220 }} placeholder="导入到指定分组" value={groupId} onChange={setGroupId}>
          {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
        </Select>
        <Button type="primary" loading={importing} disabled={!selected.length} onClick={handleImport}>
          导入选中设备（{selected.length}）
        </Button>
      </Space>

      <Table
        rowKey="ip"
        columns={columns}
        dataSource={result.results || []}
        rowSelection={{ selectedRowKeys: selected.map(x => x.ip), onChange: (_, rows) => setSelected(rows) }}
        pagination={{ pageSize: 10 }}
      />
    </Card>
  )
})
