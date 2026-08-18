import React, {useEffect, useState} from 'react';
import {observer} from 'mobx-react';
import {Card, Table, Button, Modal, Select, Tag, Space, message, Descriptions, Typography, Empty} from 'antd';
import {CloudDownloadOutlined, EyeOutlined, DiffOutlined, ReloadOutlined} from '@ant-design/icons';
import {http} from 'libs';
import store from './store';

const {Text} = Typography;

export default observer(function ConfigBackup() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [detail, setDetail] = useState(null);
  const [diffVisible, setDiffVisible] = useState(false);
  const [diff, setDiff] = useState(null);
  const [diffBase, setDiffBase] = useState(null);
  const [diffCompare, setDiffCompare] = useState(null);
  const [diffLoading, setDiffLoading] = useState(false);

  useEffect(() => {
    fetchBackups();
    setDevices(store.devices || []);
  }, []);

  function fetchBackups() {
    setLoading(true);
    http.get('/api/netmon/config-backup/', {params: {device_id: selectedDevice}}).then(res => {
      setBackups(res);
    }).finally(() => setLoading(false));
  }

  function handleTrigger(deviceId) {
    return http.post('/api/netmon/config-backup/trigger/', {device_id: deviceId}).then(res => {
      if (res.changed === false) {
        message.info(res.message);
      } else {
        message.success(res.message);
      }
      fetchBackups();
    });
  }

  function handleViewDetail(id) {
    http.get('/api/netmon/config-backup/detail/', {params: {id}}).then(res => {
      setDetail(res);
      setDetailVisible(true);
    });
  }

  function handleDiff() {
    if (!diffBase || !diffCompare) {
      message.warning('请选择两个版本进行对比');
      return;
    }
    setDiffLoading(true);
    http.post('/api/netmon/config-backup/diff/', {base_id: diffBase, compare_id: diffCompare}).then(res => {
      setDiff(res);
      setDiffVisible(true);
    }).finally(() => setDiffLoading(false));
  }

  const columns = [
    {title: '设备名称', dataIndex: 'device_name', width: 160, render: (v, r) => `${v}(${r.device_ip})`},
    {title: '备份时间', dataIndex: 'created_at', width: 180},
    {title: '配置大小', dataIndex: 'config_size', width: 100, render: v => v ? `${(v / 1024).toFixed(1)} KB` : '-'},
    {title: '配置指纹', dataIndex: 'config_hash', width: 120, render: v => v ? v.substring(0, 12) + '...' : '-'},
    {title: '备份方式', dataIndex: 'is_auto', width: 80, render: v => v ? <Tag color="blue">自动</Tag> : <Tag color="default">手动</Tag>},
    {title: '操作', width: 200, render: (_, r) => (
      <Space>
        <Button size="small" type="link" icon={<EyeOutlined/>} onClick={() => handleViewDetail(r.id)}>查看</Button>
        <Button size="small" type="link" icon={<CloudDownloadOutlined/>} loading={loading} onClick={() => handleTrigger(r.device_id)}>备份</Button>
      </Space>
    )},
  ];

  return (
    <div>
      <Card
        title="设备配置备份"
        extra={
          <Space>
            <Select
              allowClear
              placeholder="选择设备筛选"
              style={{width: 200}}
              value={selectedDevice}
              onChange={v => { setSelectedDevice(v); }}
              options={devices.map(d => ({value: d.id, label: d.name}))}
            />
            <Button icon={<ReloadOutlined/>} onClick={fetchBackups}>刷新</Button>
          </Space>
        }
      >
        <div style={{marginBottom: 16}}>
          <Space>
            <Select
              placeholder="选择设备"
              style={{width: 200}}
              options={devices.filter(d => d.host_id).map(d => ({value: d.id, label: d.name}))}
              onChange={v => handleTrigger(v)}
              prefix={<CloudDownloadOutlined/>}
            />
            <Text type="secondary">选择设备立即触发配置备份（需已关联主机）</Text>
          </Space>
        </div>
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={backups}
          pagination={{pageSize: 15}}
          locale={{emptyText: <Empty description="暂无配置备份记录"/>}}
        />
        {backups.length >= 2 && (
          <div style={{marginTop: 16, padding: 16, background: '#fafafa', borderRadius: 8}}>
            <Space>
              <Text strong>配置对比：</Text>
              <Select
                placeholder="基准版本"
                style={{width: 200}}
                value={diffBase}
                onChange={setDiffBase}
                options={backups.map(b => ({value: b.id, label: `${b.device_name} ${b.created_at}`}))}
              />
              <Text>→</Text>
              <Select
                placeholder="对比版本"
                style={{width: 200}}
                value={diffCompare}
                onChange={setDiffCompare}
                options={backups.map(b => ({value: b.id, label: `${b.device_name} ${b.created_at}`}))}
              />
              <Button type="primary" icon={<DiffOutlined/>} loading={diffLoading} onClick={handleDiff}>对比</Button>
            </Space>
          </div>
        )}
      </Card>

      <Modal
        title={detail ? `配置详情 - ${detail.device_name}` : ''}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
      >
        {detail && (
          <div>
            <Descriptions size="small" bordered column={2} style={{marginBottom: 16}}>
              <Descriptions.Item label="备份时间">{detail.created_at}</Descriptions.Item>
              <Descriptions.Item label="配置指纹">{detail.config_hash}</Descriptions.Item>
            </Descriptions>
            <pre style={{maxHeight: 500, overflow: 'auto', fontSize: 12, lineHeight: 1.5, padding: 12, background: '#f5f5f5', borderRadius: 4}}>{detail.config_text}</pre>
          </div>
        )}
      </Modal>

      <Modal
        title="配置对比"
        open={diffVisible}
        onCancel={() => setDiffVisible(false)}
        footer={null}
        width={900}
      >
        {diff && (
          <div>
            <Descriptions size="small" bordered column={2} style={{marginBottom: 16}}>
              <Descriptions.Item label="基准版本">{diff.base_at}</Descriptions.Item>
              <Descriptions.Item label="对比版本">{diff.compare_at}</Descriptions.Item>
            </Descriptions>
            {diff.is_same ? (
              <Empty description="两个版本配置完全一致，无差异"/>
            ) : (
              <pre style={{maxHeight: 500, overflow: 'auto', fontSize: 12, lineHeight: 1.5, padding: 12, background: '#f5f5f5', borderRadius: 4}}>{diff.diff}</pre>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
});