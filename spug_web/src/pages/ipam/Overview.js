/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect } from 'react';
import { observer } from 'mobx-react';
import { Row, Col, Card, Progress, Tag, Empty, Alert, Statistic } from 'antd';
import { Chart, Geom, Axis, Tooltip } from 'bizcharts';
import store from './store';

const RISK_COLOR = { low: '#52c41a', medium: '#faad14', high: '#f5222d' };
const RISK_LABEL = { low: '低风险', medium: '中风险', high: '高风险' };

export default observer(function Overview() {
  useEffect(() => { store.fetchInsights() }, []);

  const highRisk = store.insights.filter(x => x.risk_level === 'high');

  return (
    <div>
      {highRisk.length > 0 && (
        <Alert
          type="error" showIcon style={{ marginBottom: 16 }}
          message={`${highRisk.length} 个网段存在耗尽风险，请尽快关注`}
          description={highRisk.map(x => `${x.subnet_name}(${x.cidr})：${x.message}`).join('；')}
        />
      )}
      {store.insights.length === 0 && !store.insightsFetching && (
        <Empty description="暂无网段，请先在「网段管理」中添加"/>
      )}
      <Row gutter={16}>
        {store.insights.map(item => (
          <Col span={12} key={item.subnet_id} style={{ marginBottom: 16 }}>
            <Card
              title={`${item.subnet_name}（${item.cidr}）`}
              extra={<Tag color={RISK_COLOR[item.risk_level]}>{RISK_LABEL[item.risk_level]}</Tag>}
            >
              <Row gutter={16}>
                <Col span={8} style={{ textAlign: 'center' }}>
                  <Progress
                    type="dashboard" percent={item.usage_rate}
                    strokeColor={{ '0%': '#52c41a', '60%': '#faad14', '85%': '#f5222d' }}
                    format={p => `${p}%`}
                  />
                  <div style={{ color: '#8c8c8c', marginTop: 4 }}>{item.used_count}/{item.total_count} 已用</div>
                </Col>
                <Col span={16}>
                  <Statistic
                    title="预计耗尽天数"
                    value={item.days_to_exhaustion != null ? item.days_to_exhaustion : '—'}
                    suffix={item.days_to_exhaustion != null ? '天' : ''}
                    valueStyle={{ color: RISK_COLOR[item.risk_level], fontSize: 22 }}
                  />
                  <div style={{ color: '#595959', margin: '8px 0', fontSize: 12 }}>{item.message}</div>
                  {item.trend && item.trend.length >= 2 && (
                    <Chart height={100} data={item.trend} padding={[10, 10, 20, 30]} forceFit>
                      <Axis name="date" label={{ formatter: v => v.slice(5) }}/>
                      <Axis name="used_count"/>
                      <Tooltip/>
                      <Geom type="line" position="date*used_count" size={2} shape="smooth"/>
                    </Chart>
                  )}
                </Col>
              </Row>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
})
