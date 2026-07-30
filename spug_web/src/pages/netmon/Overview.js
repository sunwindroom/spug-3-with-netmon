/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect } from 'react';
import { observer } from 'mobx-react';
import { Row, Col, Card, Statistic, Progress, Table, Tag, Empty, List } from 'antd';
import {
  DesktopOutlined, CheckCircleOutlined, WarningOutlined,
  CloseCircleOutlined, QuestionCircleOutlined, ClockCircleOutlined, SafetyOutlined
} from '@ant-design/icons';
import { Chart, Geom, Coord, Legend, Tooltip, Axis } from 'bizcharts';
import store from './store';

const STATUS_COLOR = { online: '#52c41a', warning: '#faad14', critical: '#f5222d', offline: '#8c8c8c', unknown: '#d9d9d9' };
const STATUS_LABEL = { online: '正常', warning: '告警', critical: '严重', offline: '离线', unknown: '未知' };
const LEVEL_COLOR = { info: 'blue', warning: 'orange', critical: 'red' };

export default observer(function Overview() {
  useEffect(() => {
    store.fetchOverview();
  }, []);

  const ov = store.overview;
  const statusCounts = ov.status_counts || {};
  const pieData = Object.keys(STATUS_LABEL)
    .filter(k => statusCounts[k])
    .map(k => ({ status: STATUS_LABEL[k], count: statusCounts[k], color: STATUS_COLOR[k] }));

  const total = pieData.reduce((s, x) => s + x.count, 0) || 1;
  const chartData = pieData.map(x => ({ ...x, percent: x.count / total }));

  const columns = [
    { title: '级别', dataIndex: 'level_alias', width: 80, render: (v, r) => <Tag color={LEVEL_COLOR[r.level]}>{v}</Tag> },
    { title: '设备', dataIndex: 'device_name', width: 160, render: (v, r) => `${v}(${r.device_ip})` },
    { title: '指标', dataIndex: 'metric_key', width: 90 },
    { title: '说明', dataIndex: 'message' },
    { title: '时间', dataIndex: 'created_at', width: 160 },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={5}>
          <Card loading={store.ovFetching}>
            <Statistic title="设备总数" value={ov.device_total || 0} prefix={<DesktopOutlined/>}/>
          </Card>
        </Col>
        <Col span={5}>
          <Card loading={store.ovFetching}>
            <Statistic title="正常" valueStyle={{ color: STATUS_COLOR.online }}
                       value={statusCounts.online || 0} prefix={<CheckCircleOutlined/>}/>
          </Card>
        </Col>
        <Col span={5}>
          <Card loading={store.ovFetching}>
            <Statistic title="告警" valueStyle={{ color: STATUS_COLOR.warning }}
                       value={statusCounts.warning || 0} prefix={<WarningOutlined/>}/>
          </Card>
        </Col>
        <Col span={5}>
          <Card loading={store.ovFetching}>
            <Statistic title="严重" valueStyle={{ color: STATUS_COLOR.critical }}
                       value={statusCounts.critical || 0} prefix={<CloseCircleOutlined/>}/>
          </Card>
        </Col>
        <Col span={4}>
          <Card loading={store.ovFetching}>
            <Statistic title="离线/未知" valueStyle={{ color: STATUS_COLOR.offline }}
                       value={(statusCounts.offline || 0) + (statusCounts.unknown || 0)}
                       prefix={<QuestionCircleOutlined/>}/>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={8}>
          <Card title="设备健康状态分布" loading={store.ovFetching} bodyStyle={{ height: 260 }}>
            {pieData.length ? (
              <Chart height={240} data={chartData} forceFit>
                <Coord type="theta" radius={0.75} innerRadius={0.6}/>
                <Legend position="right"/>
                <Tooltip showTitle={false}/>
                <Geom
                  type="intervalStack"
                  position="percent"
                  color={['status', pieData.map(x => x.color)]}
                  tooltip={['status*percent', (status, percent) => ({
                    name: status, value: (percent * 100).toFixed(1) + '%'
                  })]}
                />
              </Chart>
            ) : <Empty description="暂无数据" style={{ paddingTop: 60 }}/>}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="集群平均 CPU 使用率" loading={store.ovFetching}>
            <div style={{ textAlign: 'center', paddingTop: 20 }}>
              <Progress
                type="dashboard"
                percent={ov.fleet_cpu_avg || 0}
                strokeColor={{ '0%': '#52c41a', '60%': '#faad14', '85%': '#f5222d' }}
                format={p => `${p}%`}
              />
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card title="集群平均内存使用率" loading={store.ovFetching}>
            <div style={{ textAlign: 'center', paddingTop: 20 }}>
              <Progress
                type="dashboard"
                percent={ov.fleet_mem_avg || 0}
                strokeColor={{ '0%': '#52c41a', '60%': '#faad14', '85%': '#f5222d' }}
                format={p => `${p}%`}
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={6}>
          <Card loading={store.ovFetching}>
            <Statistic
              title="近7天整体可用率" value={ov.availability_rate != null ? ov.availability_rate : '-'}
              suffix="%" prefix={<SafetyOutlined/>}
              valueStyle={{ color: (ov.availability_rate || 100) >= 99 ? '#52c41a' : '#faad14' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={store.ovFetching}>
            <Statistic
              title="近7天平均故障处理时长(MTTR)" value={ov.mttr_minutes != null ? ov.mttr_minutes : '-'}
              suffix="分钟" prefix={<ClockCircleOutlined/>}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="近7天故障 TOP5 设备" loading={store.ovFetching} bodyStyle={{ padding: '8px 24px' }}>
            {ov.top_faulty_7d && ov.top_faulty_7d.length ? (
              <List
                size="small"
                dataSource={ov.top_faulty_7d}
                renderItem={(item, i) => (
                  <List.Item>
                    <span><Tag color={i === 0 ? 'red' : 'default'}>{i + 1}</Tag>{item.device_name}（{item.device_ip}）</span>
                    <span>{item.count} 次</span>
                  </List.Item>
                )}
              />
            ) : <Empty description="近7天暂无故障，运行平稳" style={{ padding: '10px 0' }}/>}
          </Card>
        </Col>
      </Row>

      <Card title="近14天异常事件趋势" loading={store.ovFetching} style={{ marginBottom: 20 }}>
        {ov.anomaly_trend && ov.anomaly_trend.some(x => x.count > 0) ? (
          <Chart height={200} data={ov.anomaly_trend} padding={[10, 20, 40, 40]} forceFit>
            <Axis name="date" label={{ formatter: v => v.slice(5) }}/>
            <Axis name="count"/>
            <Tooltip/>
            <Geom type="area" position="date*count" shape="smooth" style={{ fillOpacity: 0.15 }}/>
            <Geom type="line" position="date*count" size={2} shape="smooth" color="#f5222d"/>
          </Chart>
        ) : <Empty description="近14天无异常事件，运行平稳" style={{ padding: '30px 0' }}/>}
      </Card>

      <Card title="近15分钟未处理异常" loading={store.ovFetching}>
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          columns={columns}
          dataSource={ov.top_anomalies || []}
          locale={{ emptyText: '暂无异常，一切正常' }}
        />
      </Card>
    </div>
  )
})
