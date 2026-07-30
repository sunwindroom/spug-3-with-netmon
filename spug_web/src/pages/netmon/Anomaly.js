/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Tag, Space, Select, message } from 'antd';
import { AuthButton } from 'components';
import store from './store';

const LEVEL_COLOR = { info: 'blue', warning: 'orange', critical: 'red' };
const STATUS_COLOR = { open: 'red', acknowledged: 'orange', resolved: 'green' };
const METHOD_LABEL = { threshold: '静态阈值', '3sigma': '3-sigma动态基线', ewma: 'EWMA基线' };

export default observer(function Anomaly() {
  const [status, setStatus] = useState('open');

  useEffect(() => { store.fetchAnomalies(status) }, [status]);

  function handleAck(record, next) {
    store.ackAnomaly(record.id, next).then(() => {
      message.success('操作成功');
      store.fetchAnomalies(status);
    })
  }

  const columns = [
    { title: '级别', dataIndex: 'level_alias', width: 80, render: (v, r) => <Tag color={LEVEL_COLOR[r.level]}>{v}</Tag> },
    { title: '设备', dataIndex: 'device_name', render: (v, r) => `${v}（${r.device_ip}）` },
    { title: '指标', dataIndex: 'metric_key', width: 90 },
    { title: '当前值', dataIndex: 'value', width: 90 },
    { title: '基线/阈值', dataIndex: 'baseline', width: 100 },
    { title: '判定方式', dataIndex: 'method', width: 130, render: v => METHOD_LABEL[v] || v },
    { title: '说明', dataIndex: 'message' },
    { title: '状态', dataIndex: 'status_alias', width: 90, render: (v, r) => <Tag color={STATUS_COLOR[r.status]}>{v}</Tag> },
    { title: '发生时间', dataIndex: 'created_at', width: 160 },
    {
      title: '操作', width: 160, render: (_, r) => (
        <Space>
          {r.status === 'open' &&
            <AuthButton auth="netmon.device.edit" type="link" onClick={() => handleAck(r, 'acknowledged')}>确认</AuthButton>}
          {r.status !== 'resolved' &&
            <AuthButton auth="netmon.device.edit" type="link" onClick={() => handleAck(r, 'resolved')}>标记恢复</AuthButton>}
        </Space>
      )
    }
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select style={{ width: 160 }} value={status} onChange={setStatus}>
          <Select.Option value="open">未处理</Select.Option>
          <Select.Option value="acknowledged">已确认</Select.Option>
          <Select.Option value="resolved">已恢复</Select.Option>
          <Select.Option value="">全部</Select.Option>
        </Select>
      </Space>
      <Table rowKey="id" loading={store.anomalyFetching} columns={columns} dataSource={store.anomalies}/>
    </div>
  )
})
