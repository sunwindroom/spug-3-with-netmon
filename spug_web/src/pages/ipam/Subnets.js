/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useState } from 'react';
import { observer } from 'mobx-react';
<<<<<<< HEAD
import { Table, Space, Input, InputNumber, Form, Modal, message, Progress, Switch, Tag } from 'antd';
=======
import { Table, Space, Input, InputNumber, Form, Modal, message, Progress, Switch, Tag, Checkbox, Tooltip } from 'antd';
>>>>>>> 115dece1e337a145b76b2c9fee198c5e29bd2aee
import { SearchOutlined, ImportOutlined } from '@ant-design/icons';
import { AuthButton, LinkButton } from 'components';
import { http } from 'libs';
import store from './store';

const CATEGORY_MAP = {
  server: '服务器', switch: '交换机', router: '路由器', firewall: '防火墙',
  database: '数据库', application: '应用', load_balancer: '负载均衡',
  storage: '存储', other: '其他',
};

export default observer(function Subnets() {
  const [scanning, setScanning] = useState(null);

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认', content: `确定要删除网段【${record.name}】吗？其下所有地址记录与审计日志也将被删除。`,
      onOk: () => http.delete('/api/ipam/subnet/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchSubnets() })
    })
  }

  function handleScan(record) {
    setScanning(record.id);
    store.startScan(record.id)
      .then(res => {
        const results = res.scan_results || [];
        const findings = res.findings || [];
        if (results.length === 0) {
          message.info('扫描完成，未发现存活主机');
        } else {
          message.success(`扫描完成，发现 ${results.length} 台存活主机`);
<<<<<<< HEAD
          store.showScanResult(record.id, record.name, results, findings);
=======
          store.showScanResult(record.id, results, findings);
>>>>>>> 115dece1e337a145b76b2c9fee198c5e29bd2aee
        }
      })
      .finally(() => setScanning(null))
  }

  function handleImport(record) {
    if (store.scanResults.length > 0 && store.activeScanSubnetId === record.id) {
      store.activeTab = 'scanResult';
    } else {
      message.info('请先执行扫描');
    }
  }

  const columns = [
    { title: '网段名称', dataIndex: 'name' },
    { title: 'CIDR', dataIndex: 'cidr' },
    { title: '分组', dataIndex: 'group_name', render: v => v || '-' },
    { title: '网关', dataIndex: 'gateway', render: v => v || '-' },
    {
      title: '使用率', width: 200, render: (_, r) => (
        <div>
          <Progress
            percent={r.usage_rate} size="small"
            status={r.warning ? 'exception' : 'normal'}
          />
          <span style={{ fontSize: 12, color: '#8c8c8c' }}>{r.used_count}/{r.total_count}</span>
          {r.warning && <Tag color="red" style={{ marginLeft: 4 }}>预警</Tag>}
        </div>
      )
    },
    { title: '未授权自动隔离', dataIndex: 'auto_isolate_unauthorized', render: v => v ? <Tag color="orange">已开启</Tag> : <Tag>未开启</Tag> },
    {
      title: '操作', width: 260, render: (_, r) => (
        <Space>
          <LinkButton onClick={() => { store.fetchAddresses(r.id); store.activeTab = 'addresses' }}>查看地址</LinkButton>
          <AuthButton auth="ipam.subnet.edit" type="link" loading={scanning === r.id} icon={<SearchOutlined/>}
                      onClick={() => handleScan(r)}>扫描</AuthButton>
          <AuthButton auth="ipam.subnet.edit" type="link" icon={<ImportOutlined/>}
<<<<<<< HEAD
                      onClick={() => handleImport(r)}>导入</AuthButton>
=======
                      onClick={() => store.scanResultVisible && store.activeScanSubnetId === r.id ? null : message.info('请先执行扫描')}>导入</AuthButton>
>>>>>>> 115dece1e337a145b76b2c9fee198c5e29bd2aee
          <LinkButton onClick={() => store.showSubnetForm(r)}>编辑</LinkButton>
          <AuthButton auth="ipam.subnet.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <AuthButton auth="ipam.subnet.add" type="primary" onClick={() => store.showSubnetForm()}>新建网段</AuthButton>
      </Space>
      <Table rowKey="id" loading={store.subnetFetching} columns={columns} dataSource={store.subnets}/>
      {store.subnetFormVisible && <SubnetForm/>}
      {store.scanResultVisible && <ScanResultModal/>}
    </div>
  )
})

function SubnetForm() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const record = store.subnet;

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      http.post('/api/ipam/subnet/', { ...record, ...values })
        .then(() => { message.success('保存成功'); store.subnetFormVisible = false; store.fetchSubnets() })
        .finally(() => setSaving(false))
    })
  }

  return (
    <Modal
      visible destroyOnClose title={record.id ? '编辑网段' : '新建网段'}
      confirmLoading={saving} onOk={handleSubmit}
      onCancel={() => store.subnetFormVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={record}>
        <Form.Item name="name" label="网段名称" rules={[{ required: true, message: '请输入网段名称' }]}>
          <Input placeholder="例如：办公网段-3楼"/>
        </Form.Item>
        <Form.Item name="cidr" label="CIDR" rules={[{ required: true, message: '请输入CIDR' }]}>
          <Input placeholder="例如：192.168.10.0/24" disabled={!!record.id}/>
        </Form.Item>
        <Form.Item name="gateway" label="网关地址">
          <Input placeholder="例如：192.168.10.1"/>
        </Form.Item>
        <Form.Item name="vlan_id" label="VLAN ID">
          <InputNumber style={{ width: '100%' }}/>
        </Form.Item>
        <Form.Item name="dns_servers" label="DNS服务器">
          <Input placeholder="例如：8.8.8.8,114.114.114.114"/>
        </Form.Item>
        <Form.Item name="warning_threshold" label="使用率预警阈值(%)" initialValue={80}>
          <InputNumber min={1} max={100} style={{ width: '100%' }}/>
        </Form.Item>
        <Form.Item name="auto_isolate_unauthorized" label="发现未授权设备后自动尝试隔离" valuePropName="checked" initialValue={false}>
          <Switch/>
        </Form.Item>
        <Form.Item name="desc" label="备注">
          <Input.TextArea rows={2}/>
        </Form.Item>
      </Form>
    </Modal>
  )
}

<<<<<<< HEAD
=======
function ScanResultModal() {
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [importing, setImporting] = useState(false);
  const results = store.scanResults;
  const findings = store.scanFindings;

  function handleImport() {
    if (selectedKeys.length === 0) return message.warning('请选择要导入的设备');
    const devices = results.filter(r => selectedKeys.includes(r.address));
    setImporting(true);
    store.importDiscovery(store.activeScanSubnetId, devices)
      .then(res => {
        message.success(`成功导入 ${res.count} 台设备`);
        store.scanResultVisible = false;
        store.fetchSubnets();
      })
      .finally(() => setImporting(false))
  }

  const columns = [
    { title: 'IP地址', dataIndex: 'address', width: 140 },
    { title: 'MAC地址', dataIndex: 'mac', width: 160, render: v => v || '-' },
    {
      title: '开放端口', dataIndex: 'open_ports', width: 200,
      render: v => v && v.length > 0 ? v.join(', ') : '-'
    },
    {
      title: '设备类型', dataIndex: 'category_guess', width: 100,
      render: v => <Tag color="blue">{CATEGORY_MAP[v] || v || '未知'}</Tag>
    },
  ];

  return (
    <Modal
      visible destroyOnClose title={`扫描结果（${results.length} 台存活主机）`}
      width={720} footer={null}
      onCancel={() => store.scanResultVisible = false}
    >
      {findings.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {findings.map((f, i) => (
            <Tag key={i} color={f.type === 'unauthorized' ? 'orange' : 'red'} style={{ marginBottom: 4 }}>
              {f.address}: {f.message}
            </Tag>
          ))}
        </div>
      )}
      <Table
        rowKey="address"
        columns={columns}
        dataSource={results}
        size="small"
        pagination={results.length > 10 ? { pageSize: 10 } : false}
        rowSelection={{
          selectedRowKeys: selectedKeys,
          onChange: setSelectedKeys,
        }}
      />
      <div style={{ marginTop: 12, textAlign: 'right' }}>
        <Space>
          <span>已选 {selectedKeys.length} 项</span>
          <AuthButton auth="ipam.subnet.edit" type="primary" icon={<ImportOutlined/>}
                      loading={importing} disabled={selectedKeys.length === 0}
                      onClick={handleImport}>导入选中设备</AuthButton>
        </Space>
      </div>
    </Modal>
  )
}
>>>>>>> 115dece1e337a145b76b2c9fee198c5e29bd2aee
