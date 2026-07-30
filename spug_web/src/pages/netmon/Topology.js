/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { observer } from 'mobx-react';
import { Card, Select, Empty, Space, Badge } from 'antd';
import store from './store';

const STATUS_COLOR = { online: '#52c41a', warning: '#faad14', critical: '#f5222d', offline: '#8c8c8c', unknown: '#d9d9d9' };
const CATEGORY_ICON = {
  server: '🖥️', switch: '🔀', router: '📡', firewall: '🛡️', load_balancer: '⚖️',
  storage: '💾', database: '🗄️', middleware: '🧩', application: '🧭', other: '❔',
};

// 简单的圆形布局：把节点均匀分布在一个圆周上，避免引入额外的力导向布局依赖
function circleLayout(nodes, width, height) {
  const cx = width / 2, cy = height / 2, r = Math.min(width, height) / 2 - 60;
  const n = nodes.length || 1;
  return nodes.map((node, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    return { ...node, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });
}

export default observer(function Topology() {
  const [groupId, setGroupId] = useState(undefined);
  const width = 900, height = 560;

  useEffect(() => { store.fetchTopology(groupId) }, [groupId]);

  const positioned = useMemo(
    () => circleLayout(store.topology.nodes || [], width, height),
    [store.topology.nodes]
  );
  const posMap = useMemo(() => Object.fromEntries(positioned.map(n => [n.id, n])), [positioned]);

  return (
    <Card
      title="网络拓扑"
      extra={
        <Select allowClear style={{ width: 220 }} placeholder="按分组筛选" value={groupId}
                onChange={setGroupId}>
          {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
        </Select>
      }
    >
      <Space style={{ marginBottom: 12 }}>
        {Object.entries(STATUS_COLOR).map(([k, c]) => (
          <Badge key={k} color={c} text={{ online: '正常', warning: '告警', critical: '严重', offline: '离线', unknown: '未知' }[k]}/>
        ))}
      </Space>
      {positioned.length === 0 ? (
        <Empty description="暂无设备，请先在「资源台账」中添加设备"/>
      ) : (
        <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ background: '#fafafa', borderRadius: 8 }}>
          {(store.topology.edges || []).map(edge => {
            const s = posMap[edge.source], t = posMap[edge.target];
            if (!s || !t) return null;
            return (
              <line key={edge.id} x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                    stroke="#bfbfbf" strokeWidth={edge.bandwidth_mbps ? Math.min(6, Math.max(1, edge.bandwidth_mbps / 1000)) : 1.5}/>
            )
          })}
          {positioned.map(node => (
            <g key={node.id} transform={`translate(${node.x},${node.y})`} style={{ cursor: 'pointer' }}
               onClick={() => store.showDetail(node)}>
              <circle r={26} fill="#fff" stroke={STATUS_COLOR[node.status] || '#d9d9d9'} strokeWidth={4}/>
              <text textAnchor="middle" dy={8} fontSize={20}>{CATEGORY_ICON[node.category] || '❔'}</text>
              <text textAnchor="middle" dy={44} fontSize={12} fill="#595959">{node.name}</text>
            </g>
          ))}
        </svg>
      )}
    </Card>
  )
})
