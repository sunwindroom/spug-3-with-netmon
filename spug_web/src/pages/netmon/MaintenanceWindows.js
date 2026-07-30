/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Select, Input, Form, Modal, message, Tag, Alert, DatePicker } from 'antd';
import { AuthButton, LinkButton } from 'components';
import { http } from 'libs';
import moment from 'moment';
import store from './store';

export default observer(function MaintenanceWindows() {
  useEffect(() => { store.fetchMaintenanceWindows() }, []);

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认', content: `确定要删除维护窗口【${record.name}】吗？`,
      onOk: () => http.delete('/api/netmon/maintenance-window/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchMaintenanceWindows() })
    })
  }

  const columns = [
    { title: '名称', dataIndex: 'name' },
    { title: '范围', render: (_, r) => r.device_name || r.group_name || '全局' },
    { title: '开始时间', dataIndex: 'start_at' },
    { title: '结束时间', dataIndex: 'end_at' },
    { title: '状态', dataIndex: 'is_active', render: v => v ? <Tag color="processing">生效中</Tag> : <Tag>未生效</Tag> },
    { title: '原因', dataIndex: 'reason' },
    {
      title: '操作', width: 150, render: (_, r) => (
        <Space>
          <LinkButton onClick={() => store.showMaintenanceForm(r)}>编辑</LinkButton>
          <AuthButton auth="netmon.device.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  return (
    <div>
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="计划性变更/停机期间设置维护窗口，期间该设备/分组只采集数据、不产生异常事件与告警通知，避免刷屏噪音干扰真正故障的排查判断。"
      />
      <Space style={{ marginBottom: 16 }}>
        <AuthButton auth="netmon.device.edit" type="primary" onClick={() => store.showMaintenanceForm()}>新建维护窗口</AuthButton>
      </Space>
      <Table rowKey="id" loading={store.mwFetching} columns={columns} dataSource={store.maintenanceWindows}/>
      {store.mwFormVisible && <MWForm/>}
    </div>
  )
})

function MWForm() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const record = store.maintenanceWindow;

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      const [start, end] = values.range;
      const data = {
        ...record, name: values.name, device_id: values.device_id, group_id: values.group_id,
        reason: values.reason,
        start_at: start.format('YYYY-MM-DD HH:mm:ss'),
        end_at: end.format('YYYY-MM-DD HH:mm:ss'),
      };
      http.post('/api/netmon/maintenance-window/', data)
        .then(() => { message.success('保存成功'); store.mwFormVisible = false; store.fetchMaintenanceWindows() })
        .finally(() => setSaving(false))
    })
  }

  const initialRange = record.start_at ? [moment(record.start_at), moment(record.end_at)] : undefined;

  return (
    <Modal
      visible destroyOnClose title={record.id ? '编辑维护窗口' : '新建维护窗口'}
      confirmLoading={saving} onOk={handleSubmit}
      onCancel={() => store.mwFormVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={{ ...record, range: initialRange }}>
        <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
          <Input placeholder="例如：核心交换机版本升级"/>
        </Form.Item>
        <Form.Item name="device_id" label="指定设备" help="与「指定分组」二选一，均不选表示全局维护窗口">
          <Select allowClear showSearch optionFilterProp="children">
            {store.devices.map(d => <Select.Option key={d.id} value={d.id}>{d.name}（{d.ip}）</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="group_id" label="指定分组">
          <Select allowClear>
            {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="range" label="维护时间段" rules={[{ required: true, message: '请选择时间段' }]}>
          <DatePicker.RangePicker showTime style={{ width: '100%' }}/>
        </Form.Item>
        <Form.Item name="reason" label="原因说明">
          <Input.TextArea rows={2}/>
        </Form.Item>
      </Form>
    </Modal>
  )
}
