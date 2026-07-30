/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Row, Col, Empty, Button } from 'antd';
import {
  ApiOutlined, ClusterOutlined, DatabaseOutlined, WifiOutlined,
  ApartmentOutlined, CodeOutlined, BorderOuterOutlined, FileSearchOutlined,
  BellOutlined, AppstoreOutlined, PlusOutlined, DesktopOutlined,
  HddOutlined, CloudUploadOutlined
} from '@ant-design/icons';
import { Chart, Geom, Axis, Tooltip, Coord, Legend } from 'bizcharts';
import { http } from 'libs';
import styles from './Dashboard.module.less';
import store from './store';

// 每种监控类型对应的图标 + 渐变配色，风格上呼应常见监控大屏的高识别度卡片
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

export default observer(function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    http.get('/api/monitor/dashboard/').then(res => setData(res)).finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  if (!data) return null;

  const statusPie = [
    { name: '在线', count: data.type_stats.reduce((s, x) => s + x.online, 0) },
    { name: '异常', count: data.type_stats.reduce((s, x) => s + (x.total - x.online), 0) },
  ];
  const typePie = data.type_stats.filter(x => x.total > 0).map(x => ({ name: x.type_alias, count: x.total }));

  return (
    <div>
      <div className={styles.cardGrid}>
        {data.type_stats.map(item => <TypeCard key={item.type} item={item}/>)}
      </div>

      <div className={styles.infoBar}>
        <div className={styles.infoBarItem}><BellOutlined/>最近1小时告警数：<b>{data.recent_alerts_1h}</b></div>
        <div className={styles.infoBarItem}><AppstoreOutlined/>监控资源总数：<b>{data.resource_total_count}</b></div>
        <div style={{ flex: 1 }}/>
        <Button
          type="primary" size="small" icon={<PlusOutlined/>}
          onClick={() => store.showForm()}
        >新建监控任务</Button>
      </div>

      <Row gutter={16}>
        <Col span={8}>
          <div className={styles.chartCard}>
            <div className={styles.chartTitle}>主机流量（最高/平均/最低）</div>
            <GroupedBar data={data.bar_charts.traffic} loading={loading}/>
          </div>
        </Col>
        <Col span={8}>
          <div className={styles.chartCard}>
            <div className={styles.chartTitle}>主机时延（最高/平均/最低）</div>
            <GroupedBar data={data.bar_charts.load} loading={loading}/>
          </div>
        </Col>
        <Col span={8}>
          <div className={styles.chartCard}>
            <div className={styles.chartTitle}>资源使用率（最高/平均/最低）</div>
            <GroupedBar data={data.bar_charts.usage} loading={loading}/>
          </div>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={6}>
          <div className={styles.chartCard}>
            <div className={styles.chartTitle}>内存使用率分布</div>
            <DonutChart data={data.memory_distribution} colors={['#f5222d', '#faad14', '#1890ff', '#52c41a']}/>
          </div>
        </Col>
        <Col span={6}>
          <div className={styles.chartCard}>
            <div className={styles.chartTitle}>CPU使用率分布</div>
            <DonutChart data={data.cpu_distribution} colors={['#f5222d', '#faad14', '#1890ff', '#52c41a']}/>
          </div>
        </Col>
        <Col span={6}>
          <div className={styles.chartCard}>
            <div className={styles.chartTitle}>监控资源类型分布</div>
            <DonutChart data={typePie} nameField="name"/>
          </div>
        </Col>
        <Col span={6}>
          <div className={styles.chartCard}>
            <div className={styles.chartTitle}>整体在线状态分布</div>
            <DonutChart data={statusPie} nameField="name" colors={['#52c41a', '#f5222d']}/>
          </div>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={6}>
          <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#4facfe,#00f2fe)' }}>
            <DesktopOutlined className={styles.summaryBarIcon}/>
            <div>
              <div className={styles.summaryBarLabel}>CPU核数总量</div>
              <div className={styles.summaryBarValue}>{data.resource_totals.cpu_cores}</div>
            </div>
          </div>
        </Col>
        <Col span={6}>
          <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#43e97b,#38f9d7)' }}>
            <HddOutlined className={styles.summaryBarIcon}/>
            <div>
              <div className={styles.summaryBarLabel}>内存总量(GB)</div>
              <div className={styles.summaryBarValue}>{data.resource_totals.memory_gb}</div>
            </div>
          </div>
        </Col>
        <Col span={6}>
          <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#fa709a,#fee140)' }}>
            <HddOutlined className={styles.summaryBarIcon}/>
            <div>
              <div className={styles.summaryBarLabel}>磁盘容量总量(GB)</div>
              <div className={styles.summaryBarValue}>{data.resource_totals.disk_gb}</div>
            </div>
          </div>
        </Col>
        <Col span={6}>
          <div className={styles.summaryBar} style={{ background: 'linear-gradient(135deg,#667eea,#764ba2)' }}>
            <CloudUploadOutlined className={styles.summaryBarIcon}/>
            <div>
              <div className={styles.summaryBarLabel}>传输总量(上行/下行 Kb/s)</div>
              <div className={styles.summaryBarValue}>{data.resource_totals.traffic_out_kbps} / {data.resource_totals.traffic_in_kbps}</div>
            </div>
          </div>
        </Col>
      </Row>

      {data.host_traffic.length > 0 && (
        <div className={styles.chartCard}>
          <div className={styles.chartTitle}>主机流量排行 TOP10</div>
          <Chart height={220} data={data.host_traffic} padding={[20, 20, 60, 50]} forceFit>
            <Axis name="ip" label={{ rotate: 30 }}/>
            <Axis name="value"/>
            <Tooltip/>
            <Geom type="interval" position="ip*value" color="#5B8FF9"/>
          </Chart>
        </div>
      )}
    </div>
  )
})
