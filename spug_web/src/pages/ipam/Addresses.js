/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Select, Input, Form, Modal, message, Tag, Empty, Alert } from 'antd';
import { PlusOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { AuthButton, LinkButton } from 'components';
import store from './store';

const STATUS_COLOR = {
  free: 'default', allocated: 'green', reserved: 'blue',
  released: 'default', conflict: 'red', unauthorized: 'volcano', isolated: 'magenta',
};

export default observer(function Addresses() {
  const [reserveVisible, setReserveVisible] = useState(false);
  const [editVisible, setEditVisible] = useState(false);
  const [current, setCurrent] = useState(null);

  useEffect(() => {
    if (store.activeSubnetId) store.fetchAddresses(store.activeSubnetId);
  }, []);

  function handleAllocateAuto() {
    if (!store.activeSubnetId) return message.warning('请先选择网段');
    store.allocate({ subnet_id: store.activeSubnetId })
      .then(({ error, ...ip }) => {
        if (error) return message.error(error);
        message.success(`已自动分配地址：${ip.address}`);
        store.fetchAddresses(store.activeSubnetId);
      })
  }

  function handleRelease(record) {
    Modal.confirm({
      title: '释放确认', content: `确定要释放地址【${record.address}】吗？`,
      onOk: () => store.release(record.id).then(() => {
        message.success('已释放'); store.fetchAddresses(store.activeSubnetId);
      })
    })
  }

  function handleIsolate(record) {
    Modal.confirm({
      title: '隔离确认', content: `确定要隔离地址【${record.address}】吗？系统将标记为隔离状态，如已配置隔离模板将自动执行隔离脚本。`,
      onOk: () => store.isolate(record.id).then(() => {
        message.success('已隔离'); store.fetchAddresses(store.activeSubnetId);
      })
    })
  }

  const columns = [
    { title: 'IP地址', dataIndex: 'address' },
    { title: '状态', dataIndex: 'status_alias', render: (v, r) => <Tag color={STATUS_COLOR[r.status]}>{v || '空闲'}</Tag> },
    { title: '主机名', dataIndex: 'hostname', render: v => v || '-' },
    { title: 'MAC地址', dataIndex: 'mac_address', render: v => v || '-' },
    { title: '使用人/业务', dataIndex: 'owner', render: v => v || '-' },
    { title: '关联设备', dataIndex: 'device_name', render: v => v || '-' },
    { title: '最近存活', dataIndex: 'last_seen_at', render: v => v || '-' },
    {
      title: '操作', width: 220, render: (_, r) => {
        if (r.status === 'free' || !r.id) {
          return <AuthButton auth="ipam.address.add" type="link" onClick={() => {
            store.allocate({ subnet_id: store.activeSubnetId, address: r.address })
              .then(({ error }) => {
                if (error) return message.error(error);
                message.success('分配成功'); store.fetchAddresses(store.activeSubnetId);
              })
          }}>分配</AuthButton>
        }
        return (
          <Space>
            {(r.status === 'allocated' || r.status === 'reserved') && (
              <>
                <LinkButton onClick={() => { setCurrent(r); setEditVisible(true) }}>编辑</LinkButton>
                <AuthButton auth="ipam.address.edit" type="link" onClick={() => handleRelease(r)}>释放</AuthButton>
                <AuthButton auth="ipam.address.edit" type="link" danger onClick={() => handleIsolate(r)}>隔离</AuthButton>
              </>
            )}
            {r.status === 'isolated' && (
              <AuthButton auth="ipam.address.edit" type="link" onClick={() => store.restore(r.id).then(() => {
                message.success('已解除隔离'); store.fetchAddresses(store.activeSubnetId);
              })}>解除隔离</AuthButton>
            )}
          </Space>
        )
      }
    }
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          style={{ width: 280 }} placeholder="请选择网段" value={store.activeSubnetId}
          onChange={id => store.fetchAddresses(id)}
        >
          {store.subnets.map(s => <Select.Option key={s.id} value={s.id}>{s.name}（{s.cidr}）</Select.Option>)}
        </Select>
        <AuthButton auth="ipam.address.add" type="primary" icon={<ThunderboltOutlined/>} onClick={handleAllocateAuto}>
          自动分配下一个可用地址
        </AuthButton>
        <AuthButton auth="ipam.address.edit" icon={<PlusOutlined/>} onClick={() => setReserveVisible(true)}>预留地址</AuthButton>
      </Space>
      {store.activeSubnetId ? (
        <Table rowKey="address" loading={store.addressFetching} columns={columns} dataSource={store.addresses}
               pagination={{ pageSize: 20, showSizeChanger: true }}/>
      ) : <Empty description="请先选择网段"/>}
      {reserveVisible && <ReserveForm onClose={() => setReserveVisible(false)}/>}
      {editVisible && <EditForm record={current} onClose={() => setEditVisible(false)}/>}
    </div>
  )
})

function ReserveForm({ onClose }) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      store.reserve({ subnet_id: store.activeSubnetId, ...values })
        .then(({ error }) => {
          if (error) return message.error(error);
          message.success('预留成功'); onClose(); store.fetchAddresses(store.activeSubnetId);
        })
        .finally(() => setSaving(false))
    })
  }

  return (
    <Modal visible destroyOnClose title="预留地址" confirmLoading={saving} onOk={handleSubmit} onCancel={onClose}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message="预留的地址不会被自动分配占用，可用于规划中的设备或保留网关/广播等特殊用途地址。"/>
      <Form form={form} layout="vertical">
        <Form.Item name="address" label="IP地址" rules={[{ required: true, message: '请输入要预留的地址' }]}>
          <Input placeholder="例如：192.168.10.100"/>
        </Form.Item>
        <Form.Item name="desc" label="用途说明">
          <Input.TextArea rows={2}/>
        </Form.Item>
      </Form>
    </Modal>
  )
}

function EditForm({ record, onClose }) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      store.updateAddress({ id: record.id, ...values })
        .then(() => { message.success('保存成功'); onClose(); store.fetchAddresses(store.activeSubnetId) })
        .finally(() => setSaving(false))
    })
  }

  return (
    <Modal visible destroyOnClose title={`编辑地址 - ${record.address}`} confirmLoading={saving} onOk={handleSubmit} onCancel={onClose}>
      <Form form={form} layout="vertical" initialValues={record}>
        <Form.Item name="hostname" label="主机名"><Input/></Form.Item>
        <Form.Item name="mac_address" label="MAC地址"><Input placeholder="例如：AA:BB:CC:DD:EE:FF"/></Form.Item>
        <Form.Item name="owner" label="使用人/业务"><Input/></Form.Item>
        <Form.Item name="desc" label="备注"><Input.TextArea rows={2}/></Form.Item>
      </Form>
    </Modal>
  )
}
