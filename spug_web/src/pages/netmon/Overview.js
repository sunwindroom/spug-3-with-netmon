/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect } from 'react';
import { observer } from 'mobx-react';
import { Row, Col, Card, Statistic, Progress, Table, Tag, Empty, List, Button } from 'antd';
import {
  DesktopOutlined, CheckCircleOutlined, WarningOutlined,
  CloseCircleOutlined, QuestionCircleOutlined, ClockCircleOutlined, SafetyOutlined,
  ApiOutlined, ClusterOutlined, DatabaseOutlined, WifiOutlined,
  ApartmentOutlined, CodeOutlined, BorderOuterOutlined, FileSearchOutlined,
  BellOutlined, AppstoreOutlined, PlusOutlined,
  HddOutlined, CloudUploadOutlined
} from '@ant-design/icons';
import { Chart, Geom, Coord, Legend, Tooltip, Axis } from 'bizcharts';
import { http } from 'libs';
import store from './store';
import monitorStore from '../monitor/store';
import styles from './DashboardExtra.module.less';

const STATUS_COLOR = { online: '#52c41a', warning: '#faad14', critical: '#f5222d', offline: '#8c8c8c', unknown: '#d9d9d9' };
const STATUS_LABEL = { online: '正常', warning: '告警', critical: '严重', offline: '离线', unknown: '未知' };
const LEVEL_COLOR = { info: 'blue', warning: 'orange', critical: 'red' };

const TYPE_META = {
  '1': { icon: <ApiOutlined/>, sub: '监控网站、接口', gradient: 'linear-gradient(135deg,#4facfe,#00c6fb)' },
  '2': { icon: <ApartmentOutlined/>, sub: '监控服务端口', gradient: 'linear-gradient(135deg,#f7797d,#fbd3e9)' },
  '3': { icon: <ClusterOutlined/>, sub: '监控业务进程、中间件', gradient: 'linear-gradient(135deg,#43cea2,#185a9d)' },
  '4': { icon: <CodeOutlined/>, sub: '自定义脚本，灵活扩展', gradient: 'linear-gradient(135deg,#a18cd1,#fbc2eb)' },
  '5': { icon: <WifiOutlined/>, sub: '网络设备、网关探测', gradient: 'linear-gradient(135deg,#30cfd0,#330867)' },
  '6': { icon: <BorderOuterOutlined/>, sub: '容器监控', gradient: 'linear-gradient(135deg,#0093E9,#80D0C7)' },
  '7': { icon: <DatabaseOutlined/>, sub: '数据库监听探测', gradient: 'linear-gradient(135deg,#5f72bd,#9b23ea)' },
  '8': { icon: <FileSearchOutlined/>, sub: '日志文件监控', gradient: 'linear-gradient(135deg,#f857a6,#ff5858)' },
};

function TypeCard({ item }) {
  const meta = TYPE_META[item.type] || {};
  return (
    <div className={styles.typeCard} style={{ background: meta.gradient }}>
      <div className={styles.typeCardTop}>
        <div>
          <div className={styles.typeCardTitle}>{meta.icon} &nbsp;{item.type_alias}</div>
          <div className={styles.typeCardSub}>{meta.sub}</div>
        </div>
        <div className={styles.typeCardCount}>{item.total}</div>
      </div>
      <div className={styles.typeCardBottom}>
        <span>在线{item.online}</span>
        <span>{item.rate}%</span>
      </div>
      <div style={{ padding: '0 14px 12px' }}>
        <div className={styles.typeCardBar}>
          <div className={styles.typeCardBarFill} style={{ width: `${item.rate}%` }}/>
        </div>
      </div>
    </div>
  )
}

function GroupedBar({ data, height = 220 }) {
  const rows = [];
  data.forEach(item => {
    rows.push({ metric: item.metric, series: '最高', value: item.max });
    rows.push({ metric: item.metric, series: '平均', value: item.avg });
    rows.push({ metric: item.metric, series: '最低', value: item.min });
  });
  if (!rows.length) return <Empty description="暂无数据" style={{ padding: '40px 0' }}/>;
  return (
    <Chart height={height} data={rows} padding={[20, 20, 40, 40]} forceFit>
      <Legend/>
      <Axis name="metric"/>
      <Axis name="value"/>
      <Tooltip/>
      <Geom
        type="interval"
        position="metric*value"
        color={['series', ['#5B8FF9', '#5AD8A6', '#5D7092']]}
        adjust={[{ type: 'dodge', marginRatio: 0.1 }]}
      />
    </Chart>
  )
}

function DonutChart({ data, valueField = 'count', nameField = 'range', height = 240, colors }) {
  const total = data.reduce((s, x) => s + x[valueField], 0);
  if (!total) return <Empty description="暂无数据" style={{ padding: '60px 0' }}/>;
  const chartData = data.map(x => ({ ...x, percent: x[valueField] / total }));
  return (
    <Chart height={height} data={chartData} forceFit>
      <Coord type="theta" radius={0.75} innerRadius={0.6}/>
      <Legend position="right"/>
      <Tooltip showTitle={false}/>
      <Geom
        type="intervalStack"
        position="percent"
        color={colors ? [nameField, colors] : nameField}
        tooltip={[`${nameField}*percent`, (name, percent) => ({ name, value: (percent * 100).toFixed(1) + '%' })]}
      />
    </Chart>
  )
}

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

  const typeStats = ov.type_stats || [];
  const monitorStatusPie = [
    { name: '在线', count: typeStats.reduce((s, x) => s + x.online, 0) },
    { name: '异常', count: typeStats.reduce((s, x) => s + (x.total - x.online), 0) },
  ];
  const typePie = typeStats.filter(x => x.total > 0).map(x => ({ name: x.type_alias, count: x.total }));

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

      {typeStats.length > 0 && (
        <div className={styles.cardGrid}>
          {typeStats.map(item => <TypeCard key={item.type} item={item}/>)}
        </div>
      )}

      {typeStats.length > 0 && (
        <div className={styles.infoBar}>
          <div className={styles.infoBarItem}><BellOutlined/>最近1小时告警数：<b>{ov.recent_alerts_1h || 0}</b></div>
          <div className={styles.infoBarItem}><AppstoreOutlined/>监控资源总数：<b>{ov.resource_total_count || 0}</b></div>
          <div style={{ flex: 1 }}/>
          <Button
            type="primary" size="small" icon={<PlusOutlined/>}
            onClick={() => monitorStore.showForm()}
          >新建监控任务</Button>
        </div>
      )}

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

      {ov.bar_charts && (
        <Row gutter={16}>
          <Col span={8}>
            <div className={styles.chartCard}>
              <div className={styles.chartTitle}>主机流量（最高/平均/最低）</div>
              <GroupedBar data={ov.bar_charts.traffic || []}/>
            </div>
          </Col>
          <Col span={8}>
            <div className={styles.chartCard}>
              <div className={styles.chartTitle}>主机时延（最高/平均/最低）</div>
              <GroupedBar data={ov.bar_charts.load || []}/>
            </div>
          </Col>
          <Col span={8}>
            <div className={styles.chartCard}>
              <div className={styles.chartTitle}>资源使用率（最高/平均/最低）</div>
              <GroupedBar data={ov.bar_charts.usage || []}/>
            </div>
          </Col>
        </Row>
      )}

      <Row gutter={16} style={{ marginBottom: 20 }}>
        {ov.cpu_distribution && ov.cpu_distribution.length > 0 && (
          <>
            <Col span={6}>
              <div className={styles.chartCard}>
                <div className={styles.chartTitle}>内存使用率分布</div>
                <DonutChart data={ov.memory_distribution || []} colors={['#f5222d', '#faad14', '#1890ff', '#52c41a']}/>
              </div>
            </Col>
            <Col span={6}>
              <div className={styles.chartCard}>
                <div className={styles.chartTitle}>CPU使用率分布</div>
                <DonutChart data={ov.cpu_distribution || []} colors={['#f5222d', '#faad14', '#1890ff', '#52c41a']}/>
              </div>
            </Col>
          </>
        )}
        {typePie.length > 0 && (
          <>
            <Col span={6}>
              <div className={styles.chartCard}>
                <div className={styles.chartTitle}>监控资源类型分布</div>
                <DonutChart data={typePie} nameField="name"/>
              </div>
            </Col>
            <Col span={6}>
              <div className={styles.chartCard}>
                <div className={styles.chartTitle}>整体在线状态分布</div>
                <DonutChart data={monitorStatusPie} nameField="name" colors={['#52c41a', '#f5222d']}/>
              </div>
            </Col>
          </>
        )}
      </Row>

      {ov.resource_totals && (
        <Row gutter={16}>
          <Col span={6}>
            <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#4facfe,#00f2fe)' }}>
              <DesktopOutlined className={styles.summaryBarIcon}/>
              <div>
                <div className={styles.summaryBarLabel}>CPU核数总量</div>
                <div className={styles.summaryBarValue}>{ov.resource_totals.cpu_cores}</div>
              </div>
            </div>
          </Col>
          <Col span={6}>
            <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#43e97b,#38f9d7)' }}>
              <HddOutlined className={styles.summaryBarIcon}/>
              <div>
                <div className={styles.summaryBarLabel}>内存总量(GB)</div>
                <div className={styles.summaryBarValue}>{ov.resource_totals.memory_gb}</div>
              </div>
            </div>
          </Col>
          <Col span={6}>
            <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#fa709a,#fee140)' }}>
              <HddOutlined className={styles.summaryBarIcon}/>
              <div>
                <div className={styles.summaryBarLabel}>磁盘容量总量(GB)</div>
                <div className={styles.summaryBarValue}>{ov.resource_totals.disk_gb}</div>
              </div>
            </div>
          </Col>
          <Col span={6}>
            <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#667eea,#764ba2)' }}>
              <CloudUploadOutlined className={styles.summaryBarIcon}/>
              <div>
                <div className={styles.summaryBarLabel}>传输总量(上行/下行 Kb/s)</div>
                <div className={styles.summaryBarValue}>{ov.resource_totals.traffic_out_kbps} / {ov.resource_totals.traffic_in_kbps}</div>
              </div>
            </div>
          </Col>
        </Row>
      )}

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

      {ov.host_traffic && ov.host_traffic.length > 0 && (
        <div className={styles.chartCard}>
          <div className={styles.chartTitle}>主机流量排行 TOP10</div>
          <Chart height={220} data={ov.host_traffic} padding={[20, 20, 60, 50]} forceFit>
            <Axis name="ip" label={{ rotate: 30 }}/>
            <Axis name="value"/>
            <Tooltip/>
            <Geom type="interval" position="ip*value" color="#5B8FF9"/>
          </Chart>
        </div>
      )}

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
