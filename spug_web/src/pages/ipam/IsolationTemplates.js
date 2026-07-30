/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Select, Input, Form, Modal, message, Tag, Alert, Switch } from 'antd';
import { AuthButton, LinkButton } from 'components';
import { http } from 'libs';
import netmonStore from '../netmon/store';
import store from './store';

export default observer(function IsolationTemplates() {
  useEffect(() => {
    store.fetchIsolationTemplates();
    if (!netmonStore.devices.length) netmonStore.fetchDevices();
  }, []);

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认', content: `确定要删除模板【${record.name}】吗？`,
      onOk: () => http.delete('/api/ipam/isolation-template/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchIsolationTemplates() })
    })
  }

  const columns = [
    { title: '模板名称', dataIndex: 'name' },
    { title: '执行设备', dataIndex: 'device_name' },
    { title: '默认模板', dataIndex: 'is_default', render: v => v ? <Tag color="blue">是</Tag> : '-' },
    {
      title: '操作', width: 150, render: (_, r) => (
        <Space>
          <LinkButton onClick={() => store.showTemplateForm(r)}>编辑</LinkButton>
          <AuthButton auth="ipam.subnet.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  return (
    <div>
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="隔离处置模板需绑定一台可通过SSH管理的网关/防火墙/交换机设备（在「IT资源监控-资源台账」中配置了主机凭据），脚本内容需自行编写以适配该设备型号/厂商的隔离命令（如封禁ACL、关闭端口等）。系统仅提供触发与留痕能力，不内置任何厂商私有协议。"
      />
      <Space style={{ marginBottom: 16 }}>
        <AuthButton auth="ipam.subnet.edit" type="primary" onClick={() => store.showTemplateForm()}>新建模板</AuthButton>
      </Space>
      <Table rowKey="id" loading={store.templateFetching} columns={columns} dataSource={store.isolationTemplates}/>
      {store.templateFormVisible && <TemplateForm/>}
    </div>
  )
})

function TemplateForm() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const record = store.isolationTemplate;

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      http.post('/api/ipam/isolation-template/', { ...record, ...values })
        .then(() => { message.success('保存成功'); store.templateFormVisible = false; store.fetchIsolationTemplates() })
        .finally(() => setSaving(false))
    })
  }

  return (
    <Modal
      visible destroyOnClose title={record.id ? '编辑隔离模板' : '新建隔离模板'}
      confirmLoading={saving} onOk={handleSubmit} width={600}
      onCancel={() => store.templateFormVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={record}>
        <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入模板名称' }]}>
          <Input placeholder="例如：核心交换机端口隔离"/>
        </Form.Item>
        <Form.Item name="device_id" label="执行设备" rules={[{ required: true, message: '请选择设备' }]}>
          <Select showSearch optionFilterProp="children">
            {netmonStore.devices.map(d => <Select.Option key={d.id} value={d.id}>{d.name}（{d.ip}）</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="isolate_script" label="隔离脚本" help="可使用 {ip} 占位符" rules={[{ required: true, message: '请输入隔离脚本' }]}>
          <Input.TextArea rows={3} placeholder="例如：/opt/scripts/isolate.sh {ip}"/>
        </Form.Item>
        <Form.Item name="restore_script" label="解除隔离脚本" help="可使用 {ip} 占位符">
          <Input.TextArea rows={3} placeholder="例如：/opt/scripts/restore.sh {ip}"/>
        </Form.Item>
        <Form.Item name="is_default" label="设为默认模板" valuePropName="checked" initialValue={false}
                    help="未授权设备检测/手动隔离时默认使用的模板，全局仅一个默认模板生效">
          <Switch/>
        </Form.Item>
      </Form>
    </Modal>
  )
}
