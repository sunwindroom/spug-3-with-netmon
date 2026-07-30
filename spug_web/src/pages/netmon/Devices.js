/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Tag, Space, Select, Input, Form, Modal, InputNumber, message, Upload, Button, Alert } from 'antd';
import { UploadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { AuthButton, LinkButton } from 'components';
import { http } from 'libs';
import store from './store';

const STATUS_COLOR = { online: 'green', warning: 'orange', critical: 'red', offline: 'default', unknown: 'default' };

export default observer(function Devices() {
  const [groupId, setGroupId] = useState(undefined);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [importing, setImporting] = useState(false);

  useEffect(() => { store.fetchDevices(groupId) }, [groupId]);

  const columns = [
    { title: '设备名称', dataIndex: 'name', render: (v, r) => <a onClick={() => store.showDetail(r)}>{v}</a> },
    { title: 'IP地址', dataIndex: 'ip' },
    { title: '分类', dataIndex: 'category_alias' },
    { title: '采集方式', dataIndex: 'monitor_type_alias' },
    { title: '状态', dataIndex: 'status_alias', render: (v, r) => <Tag color={STATUS_COLOR[r.status]}>{v}</Tag> },
    { title: '最近检测', dataIndex: 'latest_check_at' },
    {
      title: '操作', width: 160, render: (_, r) => (
        <Space>
          <LinkButton onClick={() => store.showForm(r)}>编辑</LinkButton>
          <AuthButton auth="netmon.device.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认',
      content: `确定要删除设备【${record.name}】吗？`,
      onOk: () => http.delete('/api/netmon/device/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchDevices(groupId) })
    })
  }

  function handleBatchDelete() {
    Modal.confirm({
      title: '批量删除确认',
      content: `确定要删除选中的 ${selectedKeys.length} 台设备吗？`,
      onOk: () => store.batchDeleteDevices(selectedKeys).then(({ deleted }) => {
        message.success(`已删除 ${deleted} 台设备`);
        setSelectedKeys([]);
        store.fetchDevices(groupId);
      })
    })
  }

  function handleImportCsv(file) {
    setImporting(true);
    store.importDevicesCsv(file)
      .then(({ created, skipped, errors }) => {
        message.success(`导入完成：新建 ${created} 台，跳过重复 ${skipped} 台${errors.length ? `，${errors.length} 行有误` : ''}`);
        if (errors.length) Modal.warning({ title: '以下行导入失败', content: errors.join('；') });
        store.fetchDevices(groupId);
      })
      .finally(() => setImporting(false));
    return false; // 阻止 Upload 组件自身上传
  }

  return (
    <div>
      <Alert
        type="info" showIcon closable style={{ marginBottom: 16 }}
        message="提示：可点击「批量导入」使用 CSV 快速录入大批量设备（表头：name,ip,category,monitor_type,group_id），或前往「自动发现」扫描网段自动识别。"
      />
      <Space style={{ marginBottom: 16 }}>
        <Select allowClear style={{ width: 220 }} placeholder="按分组筛选" value={groupId} onChange={setGroupId}>
          {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
        </Select>
        <AuthButton auth="netmon.device.add" type="primary" onClick={() => store.showForm()}>新建设备</AuthButton>
        <Upload accept=".csv" showUploadList={false} beforeUpload={handleImportCsv}>
          <AuthButton auth="netmon.device.add" icon={<UploadOutlined/>} loading={importing}>批量导入(CSV)</AuthButton>
        </Upload>
        {selectedKeys.length > 0 &&
          <AuthButton auth="netmon.device.del" danger onClick={handleBatchDelete}>批量删除（{selectedKeys.length}）</AuthButton>}
      </Space>
      <Table
        rowKey="id" loading={store.devFetching} columns={columns} dataSource={store.devices}
        rowSelection={{ selectedRowKeys: selectedKeys, onChange: setSelectedKeys }}
      />
      {store.formVisible && <DeviceForm groupId={groupId}/>}
    </div>
  )
})

function DeviceForm({ groupId }) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const record = store.device;

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      const data = { ...record, ...values };
      http.post('/api/netmon/device/', data)
        .then(() => { message.success('保存成功'); store.formVisible = false; store.fetchDevices(groupId) })
        .finally(() => setSaving(false))
    })
  }

  function handleTest() {
    form.validateFields(['ip', 'monitor_type', 'snmp_community', 'snmp_port']).then(values => {
      setTesting(true);
      store.testConnectivity({ ...record, ...values })
        .then(({ success, metrics, message: msg }) => {
          if (success) {
            Modal.success({ title: '连通性测试成功', content: `采集到指标：${JSON.stringify(metrics)}` });
          } else {
            Modal.error({ title: '连通性测试失败', content: msg });
          }
        })
        .finally(() => setTesting(false));
    })
  }

  return (
    <Modal
      visible destroyOnClose title={record.id ? '编辑设备' : '新建设备'}
      confirmLoading={saving} onOk={handleSubmit}
      onCancel={() => store.formVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={record}>
        <Form.Item name="name" label="设备名称" rules={[{ required: true, message: '请输入设备名称' }]}>
          <Input placeholder="例如：核心交换机-01"/>
        </Form.Item>
        <Form.Item name="ip" label="IP地址" rules={[{ required: true, message: '请输入IP地址' }]}>
          <Input placeholder="例如：192.168.1.1"/>
        </Form.Item>
        <Form.Item name="category" label="设备分类">
          <Select>
            {[
              ['server', '服务器'], ['switch', '交换机'], ['router', '路由器'], ['firewall', '防火墙'],
              ['load_balancer', '负载均衡'], ['storage', '存储设备'], ['database', '数据库'],
              ['middleware', '中间件'], ['application', '业务应用'], ['other', '其他'],
            ].map(([v, l]) => <Select.Option key={v} value={v}>{l}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="group_id" label="所属分组">
          <Select allowClear>
            {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="monitor_type" label="采集方式" rules={[{ required: true }]}>
          <Select>
            <Select.Option value="ping">Ping探测（时延/丢包）</Select.Option>
            <Select.Option value="snmp">SNMP采集（网络设备CPU/内存/流量）</Select.Option>
            <Select.Option value="agent">Agent采集（复用主机SSH凭据）</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.monitor_type !== cur.monitor_type}>
          {({ getFieldValue }) => getFieldValue('monitor_type') === 'snmp' && (
            <>
              <Form.Item name="snmp_community" label="SNMP团体字" initialValue="public">
                <Input/>
              </Form.Item>
              <Form.Item name="snmp_port" label="SNMP端口" initialValue={161}>
                <InputNumber style={{ width: '100%' }}/>
              </Form.Item>
            </>
          )}
        </Form.Item>
        <Form.Item name="rate" label="采集周期(秒)" initialValue={60} rules={[{ required: true }]}>
          <InputNumber min={10} style={{ width: '100%' }}/>
        </Form.Item>
        <Form.Item name="desc" label="备注">
          <Input.TextArea rows={2}/>
        </Form.Item>
        <Button icon={<ThunderboltOutlined/>} loading={testing} onClick={handleTest}>测试连通性</Button>
      </Form>
    </Modal>
  )
}
