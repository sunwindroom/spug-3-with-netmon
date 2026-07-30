/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Drawer, Descriptions, Tag, Radio, Empty, Row, Col } from 'antd';
import { Chart, Geom, Axis, Tooltip } from 'bizcharts';
import store from './store';

const STATUS_COLOR = { online: 'green', warning: 'orange', critical: 'red', offline: 'default', unknown: 'default' };
const METRICS = [
  { key: 'cpu', label: 'CPU使用率(%)' },
  { key: 'memory', label: '内存使用率(%)' },
  { key: 'rtt', label: '时延(ms)' },
  { key: 'net_in', label: '入流量(Kbps)' },
  { key: 'net_out', label: '出流量(Kbps)' },
];

function MetricChart({ deviceId, metric }) {
  const [data, setData] = useState([]);
  const [range, setRange] = useState(60);

  useEffect(() => {
    let timer;
    const load = () => store.fetchMetricHistory(deviceId, metric.key, range).then(setData);
    load();
    timer = setInterval(load, 15000);
    return () => clearInterval(timer)
  }, [deviceId, metric.key, range]);

  return (
    <Col span={12} style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <b>{metric.label}</b>
        <Radio.Group size="small" value={range} onChange={e => setRange(e.target.value)}>
          <Radio.Button value={30}>30分钟</Radio.Button>
          <Radio.Button value={60}>1小时</Radio.Button>
          <Radio.Button value={360}>6小时</Radio.Button>
        </Radio.Group>
      </div>
      {data.length ? (
        <Chart height={200} data={data} padding={[10, 20, 30, 40]} forceFit>
          <Axis name="time" label={{ formatter: v => v.slice(11, 16) }}/>
          <Axis name="value"/>
          <Tooltip crosshairs={{ type: 'x' }}/>
          <Geom type="area" position="time*value" shape="smooth" style={{ fillOpacity: 0.15 }}/>
          <Geom type="line" position="time*value" size={2} shape="smooth"/>
        </Chart>
      ) : <Empty description="暂无采集数据" style={{ padding: '40px 0' }}/>}
    </Col>
  )
}

export default observer(function DeviceDetail() {
  const device = store.device;
  if (!device || !device.id) return null;

  return (
    <Drawer
      title={`${device.name}（${device.ip}）`}
      width={760}
      visible={store.detailVisible}
      onClose={() => store.detailVisible = false}
    >
      <Descriptions column={2} size="small" bordered style={{ marginBottom: 20 }}>
        <Descriptions.Item label="状态">
          <Tag color={STATUS_COLOR[device.status]}>{device.status_alias || device.status}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="分类">{device.category_alias || device.category}</Descriptions.Item>
        <Descriptions.Item label="采集方式">{device.monitor_type_alias || device.monitor_type}</Descriptions.Item>
        <Descriptions.Item label="采集周期">{device.rate}s</Descriptions.Item>
        <Descriptions.Item label="最近检测时间" span={2}>{device.latest_check_at || '-'}</Descriptions.Item>
      </Descriptions>
      <Row gutter={16}>
        {METRICS.map(m => <MetricChart key={m.key} deviceId={device.id} metric={m}/>)}
      </Row>
    </Drawer>
  )
})
