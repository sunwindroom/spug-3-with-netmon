/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Select, Input, InputNumber, Form, Modal, message, Tag, Alert, Breadcrumb } from 'antd';
import { AuthButton, AuthDiv, LinkButton } from 'components';
import { http } from 'libs';
import store from './store';

const METRICS = [
  ['cpu', 'CPU使用率(%)'], ['memory', '内存使用率(%)'], ['disk', '磁盘使用率(%)'],
  ['rtt', '时延(ms)'], ['loss', '丢包率(%)'], ['net_in', '入流量(Kbps)'], ['net_out', '出流量(Kbps)'],
];
const LEVEL_COLOR = { info: 'blue', warning: 'orange', critical: 'red' };

export default observer(function AlertRules() {
  useEffect(() => { store.fetchAlertRules(); store.fetchDevices(); store.fetchGroups() }, []);

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认', content: `确定要删除规则【${record.name}】吗？`,
      onOk: () => http.delete('/api/netmon/alert-rule/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchAlertRules() })
    })
  }

  const columns = [
    { title: '规则名称', dataIndex: 'name' },
    { title: '指标', dataIndex: 'metric_key' },
    { title: '触发条件', render: (_, r) => `${r.operator} ${r.threshold}（连续${r.consecutive_times}次）` },
    { title: '级别', dataIndex: 'level', render: v => <Tag color={LEVEL_COLOR[v]}>{v}</Tag> },
    { title: '升级策略', render: (_, r) => r.escalate_minutes ? `超过${r.escalate_minutes}分钟未处理自动升级` : '不升级' },
    {
      title: '操作', width: 150, render: (_, r) => (
        <Space>
          <LinkButton onClick={() => store.showAlertRuleForm(r)}>编辑</LinkButton>
          <AuthButton auth="netmon.device.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  return (
    <AuthDiv auth="netmon.device.edit">
      <Breadcrumb>
        <Breadcrumb.Item>首页</Breadcrumb.Item>
        <Breadcrumb.Item>报警中心</Breadcrumb.Item>
        <Breadcrumb.Item>告警规则</Breadcrumb.Item>
      </Breadcrumb>
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="静态阈值规则用于对明确已知的红线指标（如磁盘使用率>90%）精准报警；未配置规则的指标仍会由系统的3-sigma动态基线自动兜底检测。可为规则配置「升级策略」，长时间未处理的异常会自动二次通知，避免遗漏。"
      />
      <Space style={{ marginBottom: 16 }}>
        <AuthButton auth="netmon.device.edit" type="primary" onClick={() => store.showAlertRuleForm()}>新建规则</AuthButton>
      </Space>
      <Table rowKey="id" loading={store.alertRuleFetching} columns={columns} dataSource={store.alertRules}/>
      {store.alertRuleFormVisible && <RuleForm/>}
    </AuthDiv>
  )
})

function RuleForm() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const record = store.alertRule;

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      http.post('/api/netmon/alert-rule/', { ...record, ...values })
        .then(() => { message.success('保存成功'); store.alertRuleFormVisible = false; store.fetchAlertRules() })
        .finally(() => setSaving(false))
    })
  }

  return (
    <Modal
      visible destroyOnClose title={record.id ? '编辑告警规则' : '新建告警规则'}
      confirmLoading={saving} onOk={handleSubmit}
      onCancel={() => store.alertRuleFormVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={record}>
        <Form.Item name="name" label="规则名称" rules={[{ required: true, message: '请输入规则名称' }]}>
          <Input placeholder="例如：根分区磁盘告警"/>
        </Form.Item>
        <Form.Item name="device_id" label="适用设备" help="不选择则结合下方分组或全局生效">
          <Select allowClear showSearch optionFilterProp="children">
            {store.devices.map(d => <Select.Option key={d.id} value={d.id}>{d.name}（{d.ip}）</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="group_id" label="适用分组">
          <Select allowClear>
            {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="metric_key" label="监控指标" rules={[{ required: true, message: '请选择指标' }]}>
          <Select>{METRICS.map(([v, l]) => <Select.Option key={v} value={v}>{l}</Select.Option>)}</Select>
        </Form.Item>
        <Space style={{ display: 'flex' }}>
          <Form.Item name="operator" label="比较符" rules={[{ required: true }]}>
            <Select style={{ width: 100 }}>
              {['>', '>=', '<', '<=', '=='].map(op => <Select.Option key={op} value={op}>{op}</Select.Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="threshold" label="阈值" rules={[{ required: true, message: '请输入阈值' }]}>
            <InputNumber style={{ width: 140 }}/>
          </Form.Item>
          <Form.Item name="consecutive_times" label="连续次数" initialValue={1}>
            <InputNumber min={1} style={{ width: 100 }}/>
          </Form.Item>
        </Space>
        <Form.Item name="level" label="告警级别" initialValue="warning">
          <Select>
            <Select.Option value="info">提示</Select.Option>
            <Select.Option value="warning">告警</Select.Option>
            <Select.Option value="critical">严重</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item name="escalate_minutes" label="升级策略" help="超过该时长仍未处理将自动升级二次通知，留空表示不升级">
          <InputNumber min={1} style={{ width: '100%' }} placeholder="分钟数，例如 30" addonAfter="分钟"/>
        </Form.Item>
      </Form>
    </Modal>
  )
}
