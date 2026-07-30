/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Tag, Alert, message, Modal } from 'antd';
import { AuthButton } from 'components';
import store from './store';

const STATUS_COLOR = { unauthorized: 'volcano', conflict: 'red', isolated: 'magenta' };
const STATUS_LABEL = { unauthorized: '未授权设备', conflict: 'IP冲突', isolated: '已隔离' };

export default observer(function SecurityEvents() {
  useEffect(() => { store.fetchSecurityEvents() }, []);

  function handleIsolate(record) {
    Modal.confirm({
      title: '隔离确认', content: `确定要隔离地址【${record.address}】吗？`,
      onOk: () => store.isolate(record.id).then(() => {
        message.success('已隔离'); store.fetchSecurityEvents();
      })
    })
  }

  function handleRestore(record) {
    store.restore(record.id).then(() => {
      message.success('已解除隔离'); store.fetchSecurityEvents();
    })
  }

  const columns = [
    { title: '网段', dataIndex: 'subnet_id', render: (_, r) => r.subnet_name || `#${r.subnet_id}` },
    { title: 'IP地址', dataIndex: 'address' },
    { title: '类型', dataIndex: 'status', render: v => <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v]}</Tag> },
    { title: 'MAC地址', dataIndex: 'mac_address', render: v => v || '-' },
    { title: '最近发现时间', dataIndex: 'last_seen_at', render: v => v || '-' },
    {
      title: '操作', width: 150, render: (_, r) => (
        <Space>
          {r.status !== 'isolated' &&
            <AuthButton auth="ipam.address.edit" type="link" danger onClick={() => handleIsolate(r)}>隔离</AuthButton>}
          {r.status === 'isolated' &&
            <AuthButton auth="ipam.address.edit" type="link" onClick={() => handleRestore(r)}>解除隔离</AuthButton>}
        </Space>
      )
    }
  ];

  return (
    <div>
      <Alert
        type="warning" showIcon style={{ marginBottom: 16 }}
        message="以下地址在网段扫描中被判定为未授权接入设备、IP冲突（登记MAC与实测不一致）或已处于隔离状态，建议核实后及时处置。可在「网段管理」中开启「未授权自动隔离」实现无人值守的初步响应。"
      />
      <Table rowKey="id" loading={store.securityFetching} columns={columns} dataSource={store.securityEvents}/>
    </div>
  )
})
