/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Select, Input, InputNumber, Form, Modal, message, Tag, Alert, Tabs } from 'antd';
import { AuthButton, LinkButton } from 'components';
import { http } from 'libs';
import store from './store';

export default observer(function Remediation() {
  useEffect(() => {
    store.fetchRemediationActions();
    store.fetchRemediationLogs();
  }, []);

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认', content: `确定要删除处置动作【${record.name}】吗？`,
      onOk: () => http.delete('/api/netmon/remediation-action/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchRemediationActions() })
    })
  }

  const actionColumns = [
    { title: '动作名称', dataIndex: 'name' },
    { title: '适用范围', render: (_, r) => r.device_name || r.group_name || '全部设备' },
    { title: '触发条件', render: (_, r) => `${r.metric_key || '任意指标'} 达到 ${r.level} 级别` },
    { title: '冷却时间', dataIndex: 'cooldown_minutes', render: v => `${v} 分钟` },
    {
      title: '操作', width: 150, render: (_, r) => (
        <Space>
          <LinkButton onClick={() => store.showRemediationForm(r)}>编辑</LinkButton>
          <AuthButton auth="netmon.device.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  const logColumns = [
    { title: '处置动作', dataIndex: 'action_name' },
    { title: '设备', dataIndex: 'device_name' },
    { title: '结果', dataIndex: 'success', render: v => v ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag> },
    { title: '输出', dataIndex: 'output', ellipsis: true },
    { title: '执行时间', dataIndex: 'created_at' },
  ];

  return (
    <div>
      <Alert
        type="warning" showIcon style={{ marginBottom: 16 }}
        message="故障自愈：当异常达到设定级别时，系统会自动通过设备关联主机的SSH凭据执行处置脚本（如重启服务、清理磁盘），大幅缩短常见故障的处理时长（MTTR）。请谨慎编写脚本内容，建议先在测试环境验证，并配置合理的冷却时间避免反复执行。"
      />
      <Tabs defaultActiveKey="actions">
        <Tabs.TabPane tab="处置动作配置" key="actions">
          <Space style={{ marginBottom: 16 }}>
            <AuthButton auth="netmon.device.edit" type="primary" onClick={() => store.showRemediationForm()}>新建处置动作</AuthButton>
          </Space>
          <Table rowKey="id" loading={store.remediationFetching} columns={actionColumns} dataSource={store.remediationActions}/>
        </Tabs.TabPane>
        <Tabs.TabPane tab="执行记录" key="logs">
          <Table rowKey="id" columns={logColumns} dataSource={store.remediationLogs}/>
        </Tabs.TabPane>
      </Tabs>
      {store.remediationFormVisible && <ActionForm/>}
    </div>
  )
})

function ActionForm() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const record = store.remediationAction;

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      http.post('/api/netmon/remediation-action/', { ...record, ...values })
        .then(() => { message.success('保存成功'); store.remediationFormVisible = false; store.fetchRemediationActions() })
        .finally(() => setSaving(false))
    })
  }

  return (
    <Modal
      visible destroyOnClose title={record.id ? '编辑处置动作' : '新建处置动作'}
      confirmLoading={saving} onOk={handleSubmit} width={600}
      onCancel={() => store.remediationFormVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={record}>
        <Form.Item name="name" label="动作名称" rules={[{ required: true, message: '请输入动作名称' }]}>
          <Input placeholder="例如：Nginx异常自动重启"/>
        </Form.Item>
        <Form.Item name="device_id" label="适用设备" help="需为设备关联了主机SSH凭据（在设备编辑中选择「Agent采集」时指定的主机）">
          <Select allowClear showSearch optionFilterProp="children">
            {store.devices.map(d => <Select.Option key={d.id} value={d.id}>{d.name}（{d.ip}）</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="group_id" label="适用分组">
          <Select allowClear>
            {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="metric_key" label="触发指标" help="留空表示任意指标异常均可触发">
          <Select allowClear>
            {['cpu', 'memory', 'disk', 'rtt', 'loss'].map(k => <Select.Option key={k} value={k}>{k}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="level" label="触发级别" initialValue="critical">
          <Select>
            <Select.Option value="warning">告警及以上</Select.Option>
            <Select.Option value="critical">仅严重</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item name="script" label="处置脚本" rules={[{ required: true, message: '请输入脚本内容' }]}>
          <Input.TextArea rows={5} placeholder="例如：systemctl restart nginx"/>
        </Form.Item>
        <Form.Item name="cooldown_minutes" label="冷却时间(分钟)" initialValue={15}>
          <InputNumber min={1} style={{ width: '100%' }}/>
        </Form.Item>
      </Form>
    </Modal>
  )
}
