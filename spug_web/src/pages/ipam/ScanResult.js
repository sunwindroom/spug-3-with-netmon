import React, { useState, useEffect } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Input, InputNumber, Form, Modal, Select, message, Tag, Popconfirm, Button } from 'antd';
import { ImportOutlined, DeleteOutlined } from '@ant-design/icons';
import { AuthButton } from 'components';
import { http } from 'libs';
import store from './store';

const CATEGORY_MAP = {
  server: '服务器', switch: '交换机', router: '路由器', firewall: '防火墙',
  database: '数据库', application: '应用', load_balancer: '负载均衡',
  storage: '存储', other: '其他',
};

export default observer(function ScanResult() {
  const [hostGroups, setHostGroups] = useState([]);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [importing, setImporting] = useState(false);
  const [editRecord, setEditRecord] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const results = store.scanResults;
  const findings = store.scanFindings;

  useEffect(() => {
    http.get('/api/host/group/').then(res => {
      const flat = [];
      const walk = (items) => {
        for (const item of items) {
          flat.push({ id: item.key, name: item.title });
          if (item.children && item.children.length > 0) walk(item.children);
        }
      };
      walk(res.treeData || []);
      setHostGroups(flat);
    });
  }, []);

  function handleEdit(record) {
    setEditRecord({
      address: record.address,
      mac: record.mac,
      category_guess: record.category_guess,
      open_ports: record.open_ports,
      registered: record.registered,
      host_name: record.host_name || record.address,
      host_hostname: record.host_hostname || record.address,
      host_port: record.host_port || 22,
      host_username: record.host_username || 'root',
      host_password: record.host_password || '',
      host_pkey: record.host_pkey || '',
      host_group_id: record.host_group_id || null,
      host_group_name: record.host_group_name || '',
    });
    setTestResult(null);
  }

  function handleTest() {
    if (!editRecord.host_hostname) return message.warning('请填写连接地址');
    setTesting(true);
    setTestResult(null);
    http.post('/api/ipam/scan/test/', {
      hostname: editRecord.host_hostname,
      port: editRecord.host_port || 22,
      username: editRecord.host_username || 'root',
      password: editRecord.host_password || '',
      pkey: editRecord.host_pkey || '',
    }).then(res => {
      setTestResult(res);
    }).finally(() => setTesting(false));
  }

  function handleSaveEdit() {
    const idx = store.scanResults.findIndex(r => r.address === editRecord.address);
    if (idx >= 0) {
      store.scanResults[idx] = { ...store.scanResults[idx], ...editRecord };
      store.scanResults = [...store.scanResults];
    }
    message.success('编辑已保存，请勾选后点击"导入选中设备"以创建到主机管理');
    setEditRecord(null);
  }

  function handleImport() {
    if (selectedKeys.length === 0) return message.warning('请选择要导入的设备');
    const devices = results.filter(r => selectedKeys.includes(r.address)).map(r => ({
      address: r.address,
      mac: r.mac,
      category_guess: r.category_guess,
      host_name: r.host_name || r.address,
      host_hostname: r.host_hostname || r.address,
      host_port: r.host_port || 22,
      host_username: r.host_username || 'root',
      host_password: r.host_password || '',
      host_pkey: r.host_pkey || '',
      host_group_id: r.host_group_id || null,
    }));
    setImporting(true);
    store.importDiscovery(store.activeScanSubnetId, devices)
      .then(res => {
        const errMsgs = (res.errors || []);
        if (errMsgs.length > 0) {
          errMsgs.forEach(e => message.warning(e));
        }
        if (res.count > 0) {
          message.success(`成功导入 ${res.count} 台设备到主机管理`);
        }
        const importedAddrs = (res.imported || []).map(x => x.address);
        store.scanResults = store.scanResults.map(r => {
          if (importedAddrs.includes(r.address)) {
            return { ...r, registered: true };
          }
          return r;
        });
        setSelectedKeys([]);
        store.fetchSubnets();
      })
      .finally(() => setImporting(false))
  }

  const columns = [
    { title: 'IP地址', dataIndex: 'address', width: 130 },
    { title: 'MAC地址', dataIndex: 'mac', width: 140, render: v => v || '-' },
    {
      title: '开放端口', dataIndex: 'open_ports', width: 180,
      render: v => v && v.length > 0 ? v.join(', ') : '-'
    },
    {
      title: '设备类型', dataIndex: 'category_guess', width: 90,
      render: v => <Tag color="blue">{CATEGORY_MAP[v] || v || '未知'}</Tag>
    },
    {
      title: '状态', width: 80, dataIndex: 'registered',
      render: v => v ? <Tag color="green">已登记</Tag> : <Tag color="orange">未登记</Tag>
    },
    { title: '主机名称', dataIndex: 'host_name', width: 120, render: v => v || '-' },
    { title: '连接地址', dataIndex: 'host_hostname', width: 130, render: v => v || '-' },
    { title: '端口', dataIndex: 'host_port', width: 60, render: v => v || '-' },
    { title: '用户名', dataIndex: 'host_username', width: 80, render: v => v || '-' },
    { title: '主机分组', dataIndex: 'host_group_name', width: 100, render: v => v || '-' },
    {
      title: '操作', width: 80, render: (_, r) => (
        <a onClick={() => handleEdit(r)}>编辑</a>
      )
    },
  ];

  if (results.length === 0) {
    return <div style={{ padding: 24, color: '#999', textAlign: 'center' }}>暂无扫描结果，请先在网段管理中执行扫描</div>;
  }

  return (
    <div>
      {findings.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {findings.map((f, i) => (
            <Tag key={i} color={f.type === 'unauthorized' ? 'orange' : 'red'} style={{ marginBottom: 4 }}>
              {f.address}: {f.message}
            </Tag>
          ))}
        </div>
      )}
      <Table
        rowKey="address"
        columns={columns}
        dataSource={results}
        size="small"
        scroll={{ x: 1200 }}
        pagination={results.length > 10 ? { pageSize: 10 } : false}
        rowSelection={{
          selectedRowKeys: selectedKeys,
          onChange: setSelectedKeys,
          getCheckboxProps: r => ({ disabled: r.registered }),
        }}
      />
      <div style={{ marginTop: 12, textAlign: 'right' }}>
        <Space>
          <span>已选 {selectedKeys.length} 项</span>
          <Popconfirm title="确定清除扫描结果？" onConfirm={() => { store.clearScanResult(); setSelectedKeys([]); }}>
            <AuthButton auth="ipam.subnet.edit" type="default" icon={<DeleteOutlined/>}>清除结果</AuthButton>
          </Popconfirm>
          <AuthButton auth="ipam.subnet.edit" type="primary" icon={<ImportOutlined/>}
                      loading={importing} disabled={selectedKeys.length === 0}
                      onClick={handleImport}>导入选中设备</AuthButton>
        </Space>
      </div>
      {editRecord && (
        <Modal
          visible destroyOnClose title={`编辑设备 ${editRecord.address}`}
          width={520}
          onCancel={() => setEditRecord(null)}
          footer={[
            <Button key="cancel" onClick={() => setEditRecord(null)}>取消</Button>,
            <Button key="test" loading={testing} onClick={handleTest}>测试连接</Button>,
            <Button key="save" type="primary" onClick={handleSaveEdit}>保存</Button>,
          ]}
        >
          <Form layout="vertical">
            <Form.Item label="主机名称">
              <Input value={editRecord.host_name}
                     onChange={e => setEditRecord({ ...editRecord, host_name: e.target.value })}/>
            </Form.Item>
            <Form.Item label="连接地址">
              <Input value={editRecord.host_hostname}
                     onChange={e => setEditRecord({ ...editRecord, host_hostname: e.target.value })}/>
            </Form.Item>
            <Form.Item label="SSH端口">
              <InputNumber value={editRecord.host_port} style={{ width: '100%' }}
                           onChange={v => setEditRecord({ ...editRecord, host_port: v })}/>
            </Form.Item>
            <Form.Item label="用户名">
              <Input value={editRecord.host_username}
                     onChange={e => setEditRecord({ ...editRecord, host_username: e.target.value })}/>
            </Form.Item>
            <Form.Item label="密码">
              <Input.Password placeholder="SSH密码（可选）"
                              value={editRecord.host_password}
                              onChange={e => setEditRecord({ ...editRecord, host_password: e.target.value })}/>
            </Form.Item>
            <Form.Item label="密钥">
              <Input.TextArea rows={2} placeholder="SSH私钥内容（可选）"
                              value={editRecord.host_pkey}
                              onChange={e => setEditRecord({ ...editRecord, host_pkey: e.target.value })}/>
            </Form.Item>
            <Form.Item label="主机分组">
              <Select allowClear placeholder="选择主机分组" style={{ width: '100%' }}
                      value={editRecord.host_group_id || undefined}
                      onChange={(v) => {
                        const grp = hostGroups.find(g => g.id === v);
                        setEditRecord({ ...editRecord, host_group_id: v, host_group_name: grp ? grp.name : '' });
                      }}>
                {hostGroups.map(g => <Select.Option key={g.id} value={g.id}>{g.name}</Select.Option>)}
              </Select>
            </Form.Item>
          </Form>
          {testResult && (
            <div style={{ marginTop: 8 }}>
              {testResult.ok
                ? <Tag color="green" style={{ fontSize: 14, padding: '4px 12px' }}>✓ {testResult.message}</Tag>
                : <Tag color="red" style={{ fontSize: 14, padding: '4px 12px' }}>✗ {testResult.message}</Tag>
              }
            </div>
          )}
        </Modal>
      )}
    </div>
  )
})
