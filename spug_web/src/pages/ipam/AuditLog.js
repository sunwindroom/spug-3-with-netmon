/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Select, Input, DatePicker, Button, Tag, Popover } from 'antd';
import store from './store';

const ACTION_COLOR = {
  allocate: 'green', release: 'default', reserve: 'blue', update: 'gold',
  conflict: 'red', unauthorized: 'volcano', isolate: 'magenta', restore: 'cyan',
};

export default observer(function AuditLog() {
  const [filters, setFilters] = useState({});

  useEffect(() => { store.fetchChangeLogs() }, []);

  function handleSearch() {
    const params = { ...filters };
    if (filters.range) {
      params.start = filters.range[0].format('YYYY-MM-DD 00:00:00');
      params.end = filters.range[1].format('YYYY-MM-DD 23:59:59');
      delete params.range;
    }
    store.fetchChangeLogs(params);
  }

  const columns = [
    { title: '时间', dataIndex: 'created_at', width: 160 },
    { title: '网段', dataIndex: 'subnet_id', width: 140, render: v => store.subnets.find(s => s.id === v)?.name || `#${v}` },
    { title: '地址', dataIndex: 'address', width: 130 },
    { title: '操作类型', dataIndex: 'action_alias', width: 100, render: (v, r) => <Tag color={ACTION_COLOR[r.action]}>{v}</Tag> },
    { title: '操作人', dataIndex: 'operator_name', width: 100 },
    {
      title: '变更内容', render: (_, r) => {
        if (!r.before && !r.after) return r.remark || '-';
        return (
          <Popover content={<pre style={{ maxWidth: 400, whiteSpace: 'pre-wrap' }}>
            {'变更前：' + JSON.stringify(r.before) + '\n变更后：' + JSON.stringify(r.after)}
          </pre>}>
            <a>查看详情{r.remark ? `（${r.remark}）` : ''}</a>
          </Popover>
        )
      }
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Select allowClear style={{ width: 200 }} placeholder="按网段筛选"
                onChange={v => setFilters({ ...filters, subnet_id: v })}>
          {store.subnets.map(s => <Select.Option key={s.id} value={s.id}>{s.name}</Select.Option>)}
        </Select>
        <Input
          style={{ width: 160 }} placeholder="按地址搜索"
          onChange={e => setFilters({ ...filters, address: e.target.value })}
        />
        <Select allowClear style={{ width: 150 }} placeholder="按操作类型筛选"
                onChange={v => setFilters({ ...filters, action: v })}>
          {Object.entries(ACTION_COLOR).map(([k]) => <Select.Option key={k} value={k}>{k}</Select.Option>)}
        </Select>
        <DatePicker.RangePicker onChange={v => setFilters({ ...filters, range: v })}/>
        <Button type="primary" onClick={handleSearch}>查询</Button>
      </Space>
      <Table rowKey="id" loading={store.logFetching} columns={columns} dataSource={store.changeLogs}/>
    </div>
  )
})
