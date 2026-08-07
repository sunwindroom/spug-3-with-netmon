/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import {
  Table, Tag, Space, Select, Input, Form, Modal, InputNumber, message, Upload, Button, Alert, TreeSelect,
  Radio, Checkbox, Transfer, Divider
} from 'antd';
import { UploadOutlined, ThunderboltOutlined, SearchOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { AuthButton, LinkButton, ACEditor } from 'components';
import { http, cleanCommand } from 'libs';
import store from './store';
import hostStore from 'pages/host/store';
import groupStore from '../alarm/group/store';
import HostSelector from 'pages/host/Selector';
import TemplateSelector from '../exec/task/TemplateSelector';

const STATUS_COLOR = { online: 'green', warning: 'orange', critical: 'red', offline: 'default', unknown: 'default' };

// 指标采集类型：写入 MetricRecord，走 AlertRule / 动态基线做异常检测
const METRIC_TYPE_OPTIONS = [
  ['ping', 'Ping探测（时延/丢包）'],
  ['snmp', 'SNMP采集（网络设备CPU/内存/流量）'],
  ['agent', 'Agent采集（复用主机SSH凭据）'],
  ['script', '自定义采集脚本（数值型，通过SSH执行）'],
];
// 可用性检测类型：合并自原"监控中心"模块，走连续失败阈值 + 静默期告警
const CHECK_TYPE_OPTIONS = [
  ['http', 'HTTP/站点检测'],
  ['port', '端口检测'],
  ['database', '数据库端口检测'],
  ['ping_check', 'Ping可用性检测（阈值告警）'],
  ['process', '进程检测（需绑定主机）'],
  ['docker', 'Docker容器检测（需绑定主机）'],
  ['shell', '命令检测/退出码（需绑定主机）'],
  ['log', '日志关键字监控（需绑定主机）'],
];
function IpInputField({ form, record }) {
  const [selectedHostIds, setSelectedHostIds] = useState([]);

  function handleHostSelectorChange(rows) {
    const list = Array.isArray(rows) ? rows : [rows];
    setSelectedHostIds(list.map(h => h.id));
    if (list.length === 1) {
      const h = list[0];
      const ip = (h.private_ip_address && h.private_ip_address[0])
        || (h.public_ip_address && h.public_ip_address[0])
        || h.hostname || '';
      form.setFieldsValue({ ip, host_id: h.id });
    } else if (list.length > 1) {
      const ips = list.map(h =>
        (h.private_ip_address && h.private_ip_address[0])
        || (h.public_ip_address && h.public_ip_address[0])
        || h.hostname || ''
      ).join(', ');
      form.setFieldsValue({ ip: ips, host_id: list[0].id });
    }
  }

  const suffix = selectedHostIds.length > 0 ? (
    <HostSelector mode="rows" onlyOne={false} value={selectedHostIds} onChange={handleHostSelectorChange}>
      <SearchOutlined style={{ color: '#1890ff', cursor: 'pointer' }}/>
    </HostSelector>
  ) : (
    <HostSelector mode="rows" onlyOne={false} value={[]} onChange={handleHostSelectorChange}>
      <SearchOutlined style={{ color: '#bfbfbf', cursor: 'pointer' }}/>
    </HostSelector>
  );

  return (
    <Form.Item name="ip" label="IP地址" rules={[{ required: true, message: '请输入IP地址或点击右侧图标选择主机' }]}
      extra={selectedHostIds.length > 0 ? `已关联 ${selectedHostIds.length} 台主机（点击输入框右侧图标可重新选择）` : '可手动输入IP，或点击右侧图标从主机管理中选择'}>
      <Input placeholder="例如：192.168.1.1" suffix={suffix} allowClear
        onChange={e => { if (!e.target.value) setSelectedHostIds([]) }}/>
    </Form.Item>
  );
}

const CHECK_TYPES = CHECK_TYPE_OPTIONS.map(x => x[0]);
const HOST_REQUIRED_TYPES = ['process', 'docker', 'shell', 'log'];

const NOTIFY_MODE_OPTIONS = [
  { label: '微信', value: '1' },
  { label: '短信', value: '2' },
  { label: '钉钉', value: '3' },
  { label: '邮件', value: '4' },
  { label: '企业微信', value: '5' },
  { label: '电话', value: '6' },
  { label: '飞书', value: '7' },
];

export default observer(function Devices() {
  const [groupId, setGroupId] = useState(undefined);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [importing, setImporting] = useState(false);

  useEffect(() => { store.fetchDevices(groupId) }, [groupId]);
  useEffect(() => {
    if (groupStore.records.length === 0) groupStore.fetchRecords();
    if (hostStore.initial) { hostStore.initial() } else if (hostStore.fetchRecords) { hostStore.fetchRecords() }
  }, []);

  const columns = [
    { title: '设备名称', dataIndex: 'name', render: (v, r) => <a onClick={() => store.showDetail(r)}>{v}</a> },
    { title: 'IP地址/目标', dataIndex: 'ip' },
    { title: '分类', dataIndex: 'category_alias' },
    {
      title: '监控方式', dataIndex: 'monitor_type_alias',
      render: (v, r) => <Tag color={r.is_check_type ? 'blue' : 'purple'}>{v}</Tag>
    },
    { title: '状态', dataIndex: 'status_alias', render: (v, r) => <Tag color={STATUS_COLOR[r.status]}>{v}</Tag> },
    { title: '最近检测', dataIndex: 'latest_check_at' },
    {
      title: '操作', width: 160, render: (_, r) => (
        <Space>
          <LinkButton onClick={() => store.showForm(r)}>编辑</LinkButton>
          <AuthButton auth="netmon.device.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认',
      content: `确定要删除设备【${record.name}】吗？`,
      onOk: () => http.delete('/api/netmon/device/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchDevices(groupId) })
    })
  }

  function handleBatchDelete() {
    Modal.confirm({
      title: '批量删除确认',
      content: `确定要删除选中的 ${selectedKeys.length} 台设备吗？`,
      onOk: () => store.batchDeleteDevices(selectedKeys).then(({ deleted }) => {
        message.success(`已删除 ${deleted} 台设备`);
        setSelectedKeys([]);
        store.fetchDevices(groupId);
      })
    })
  }

  function handleImportCsv(file) {
    setImporting(true);
    store.importDevicesCsv(file)
      .then(({ created, skipped, errors }) => {
        message.success(`导入完成：新建 ${created} 台，跳过重复 ${skipped} 台${errors.length ? `，${errors.length} 行有误` : ''}`);
        if (errors.length) Modal.warning({ title: '以下行导入失败', content: errors.join('；') });
        store.fetchDevices(groupId);
      })
      .finally(() => setImporting(false));
    return false; // 阻止 Upload 组件自身上传
  }

  return (
    <div>
      <Alert
        type="info" showIcon closable style={{ marginBottom: 16 }}
        message="提示：本页面已统一原「监控中心」与「IT资源监控」两套功能——网络设备指标采集、站点/端口/进程/Docker/日志等可用性检测、告警联系组与通知渠道，现在都在这一处维护，不再有两套互不相通的数据。可点击「批量导入」使用 CSV 快速录入大批量设备，或前往「自动发现」扫描网段自动识别。"
      />
      <Space style={{ marginBottom: 16 }}>
        <TreeSelect allowClear style={{ width: 220 }} placeholder="按分组筛选" value={groupId} onChange={setGroupId}
          treeData={store.treeData} treeNodeFilterProp="title" showSearch treeDefaultExpandAll/>
        <AuthButton auth="netmon.device.add" type="primary" onClick={() => store.showForm()}>新建监控项</AuthButton>
        <Upload accept=".csv" showUploadList={false} beforeUpload={handleImportCsv}>
          <AuthButton auth="netmon.device.add" icon={<UploadOutlined/>} loading={importing}>批量导入(CSV)</AuthButton>
        </Upload>
        {selectedKeys.length > 0 &&
          <AuthButton auth="netmon.device.del" danger onClick={handleBatchDelete}>批量删除（{selectedKeys.length}）</AuthButton>}
      </Space>
      <Table
        rowKey="id" loading={store.devFetching} columns={columns} dataSource={store.devices}
        rowSelection={{ selectedRowKeys: selectedKeys, onChange: setSelectedKeys }}
      />
      {store.formVisible && <DeviceForm groupId={groupId}/>}
    </div>
  )
})

function parseExtra(raw) {
  if (!raw) return {};
  try {
    const data = JSON.parse(raw);
    return typeof data === 'object' && data !== null ? data : {};
  } catch (e) {
    return {};
  }
}

function buildExtra(monitorType, values) {
  switch (monitorType) {
    case 'http':
      return JSON.stringify({ url: values.chk_url, timeout_limit_ms: values.chk_timeout_limit_ms || undefined });
    case 'port':
    case 'database':
      return JSON.stringify({ port: values.chk_port });
    case 'process':
      return JSON.stringify({ keyword: values.chk_keyword });
    case 'docker':
      return JSON.stringify({ container: values.chk_container });
    case 'log':
      return JSON.stringify({ path: values.chk_log_path, keyword: values.chk_log_keyword, tail_lines: values.chk_log_tail_lines || 200 });
    case 'shell':
      return values.chk_script || '';
    case 'script':
      return values.extra || '';
    default:
      return values.extra || '';
  }
}

export function DeviceForm({ groupId }) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showTmp, setShowTmp] = useState(false);
  const record = store.device;
  const parsedExtra = parseExtra(record.extra);

  useEffect(() => {
    if (hostStore.rawRecords.length === 0) {
      if (hostStore.initial) { hostStore.initial() } else if (hostStore.fetchRecords) { hostStore.fetchRecords() }
    }
  }, []);

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      const extra = buildExtra(values.monitor_type, values);
      const data = {
        ...record, ...values, extra,
        notify_grp: values.notify_grp || [],
        notify_mode: values.notify_mode || [],
      };
      // 这些是仅用于表单交互的临时字段，提交前清理掉，避免污染后端参数
      Object.keys(data).forEach(k => { if (k.startsWith('chk_') || k.startsWith('_')) delete data[k] });
      http.post('/api/netmon/device/', data)
        .then(() => { message.success('保存成功'); store.formVisible = false; store.fetchDevices(groupId) })
        .finally(() => setSaving(false))
    })
  }

  function handleTest() {
    form.validateFields().then(values => {
      setTesting(true);
      const extra = buildExtra(values.monitor_type, values);
      store.testConnectivity({ ...record, ...values, extra })
        .then(({ success, metrics, message: msg }) => {
          if (success) {
            Modal.success({ title: '连通性/可用性测试成功', content: metrics ? `采集到指标：${JSON.stringify(metrics)}` : msg });
          } else {
            Modal.error({ title: '连通性/可用性测试失败', content: msg });
          }
        })
        .finally(() => setTesting(false));
    })
  }

  return (
    <Modal
      visible destroyOnClose width={640} title={record.id ? '编辑监控项' : '新建监控项'}
      confirmLoading={saving} onOk={handleSubmit}
      onCancel={() => store.formVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={{
        ...record,
        chk_url: parsedExtra.url || (record.monitor_type === 'http' ? record.ip : undefined),
        chk_timeout_limit_ms: parsedExtra.timeout_limit_ms,
        chk_port: parsedExtra.port,
        chk_keyword: parsedExtra.keyword,
        chk_container: parsedExtra.container,
        chk_log_path: parsedExtra.path,
        chk_log_keyword: parsedExtra.keyword,
        chk_log_tail_lines: parsedExtra.tail_lines || 200,
        chk_script: record.monitor_type === 'shell' ? (record.extra || '') : undefined,
        notify_grp: record.notify_grp || [],
        notify_mode: record.notify_mode || [],
      }}>
        <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
          <Input placeholder="例如：核心交换机-01 / 官网首页可用性"/>
        </Form.Item>
        <Form.Item name="group_id" label="所属分组">
          <TreeSelect
            allowClear
            showSearch
            treeNodeFilterProp="title"
            treeData={store.treeData}
            treeDefaultExpandAll
            placeholder="请选择分组（与主机管理共享）"/>
        </Form.Item>
        <Form.Item name="category" label="设备分类" initialValue="server">
          <Select>
            {[
              ['server', '服务器'], ['switch', '交换机'], ['router', '路由器'], ['firewall', '防火墙'],
              ['load_balancer', '负载均衡'], ['storage', '存储设备'], ['database', '数据库'],
              ['middleware', '中间件'], ['application', '业务应用'], ['other', '其他'],
            ].map(([v, l]) => <Select.Option key={v} value={v}>{l}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="monitor_type" label="监控方式" initialValue="ping" rules={[{ required: true }]}>
          <Select>
            <Select.OptGroup label="指标采集（数值趋势 + 动态基线异常检测）">
              {METRIC_TYPE_OPTIONS.map(([v, l]) => <Select.Option key={v} value={v}>{l}</Select.Option>)}
            </Select.OptGroup>
            <Select.OptGroup label="可用性检测（是/否正常，连续失败达阈值告警）">
              {CHECK_TYPE_OPTIONS.map(([v, l]) => <Select.Option key={v} value={v}>{l}</Select.Option>)}
            </Select.OptGroup>
          </Select>
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(p, c) => p.monitor_type !== c.monitor_type}>
          {({ getFieldValue }) => {
            const mt = getFieldValue('monitor_type');
            const needHost = HOST_REQUIRED_TYPES.includes(mt);
            return (
              <>
                {/* IP地址：指标采集类型 与 端口/数据库/Ping可用性检测 都需要 */}
                {['ping', 'snmp', 'agent', 'script', 'port', 'database', 'ping_check'].includes(mt) && (
                  <IpInputField form={form} record={record}/>
                )}

                {mt === 'snmp' && (
                  <>
                    <Form.Item name="snmp_community" label="SNMP团体字" initialValue="public">
                      <Input/>
                    </Form.Item>
                    <Form.Item name="snmp_port" label="SNMP端口" initialValue={161}>
                      <InputNumber style={{ width: '100%' }}/>
                    </Form.Item>
                  </>
                )}

                {mt === 'script' && (
                  <Form.Item
                    required
                    label="采集脚本内容（需在标准输出打印 key=value 形式的数值指标）"
                    extra={<LinkButton onClick={() => setShowTmp(true)}>从模板添加</LinkButton>}>
                    <ACEditor
                      mode="sh"
                      value={record.monitor_type === 'script' ? (record.extra || '') : ''}
                      width="100%"
                      height="160px"
                      onChange={e => { record.extra = cleanCommand(e); form.setFieldsValue({ extra: cleanCommand(e) }) }}/>
                  </Form.Item>
                )}

                {mt === 'http' && (
                  <>
                    <Form.Item name="chk_url" label="检测URL" rules={[{ required: true, message: '请输入检测URL' }]}>
                      <Input placeholder="例如：https://www.example.com"/>
                    </Form.Item>
                    <Form.Item name="chk_timeout_limit_ms" label="响应时间告警阈值(ms，选填)">
                      <InputNumber min={1} style={{ width: '100%' }} placeholder="不填则只检测HTTP状态码是否正常"/>
                    </Form.Item>
                  </>
                )}

                {(mt === 'port' || mt === 'database') && (
                  <Form.Item name="chk_port" label="检测端口" rules={[{ required: true, message: '请输入端口号' }]}>
                    <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="例如：3306"/>
                  </Form.Item>
                )}

                {needHost && (
                  <Form.Item name="host_id" label="绑定主机" rules={[{ required: true, message: '该检测方式需要通过SSH在目标主机上执行，请绑定主机' }]}>
                    <Select showSearch placeholder="请选择主机" optionFilterProp="children">
                      {(hostStore.rawRecords || []).map(item => (
                        <Select.Option key={item.id} value={item.id}>{`${item.name}(${item.hostname})`}</Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                )}

                {mt === 'process' && (
                  <Form.Item name="chk_keyword" label="进程关键字" rules={[{ required: true, message: '请输入进程关键字' }]}>
                    <Input placeholder="用于 ps -ef | grep 匹配，例如：nginx"/>
                  </Form.Item>
                )}

                {mt === 'docker' && (
                  <Form.Item name="chk_container" label="容器名称" rules={[{ required: true, message: '请输入容器名称' }]}>
                    <Input placeholder="例如：spug_web"/>
                  </Form.Item>
                )}

                {mt === 'shell' && (
                  <Form.Item name="chk_script" label="检测脚本（退出码为0视为正常）" rules={[{ required: true, message: '请输入检测脚本' }]}>
                    <ACEditor
                      mode="sh"
                      value={form.getFieldValue('chk_script') || ''}
                      width="100%"
                      height="140px"
                      onChange={e => form.setFieldsValue({ chk_script: cleanCommand(e) })}/>
                  </Form.Item>
                )}

                {mt === 'log' && (
                  <>
                    <Form.Item name="chk_log_path" label="日志文件路径" rules={[{ required: true, message: '请输入日志文件路径' }]}>
                      <Input placeholder="例如：/var/log/app/error.log"/>
                    </Form.Item>
                    <Form.Item name="chk_log_keyword" label="告警关键字" rules={[{ required: true, message: '请输入关键字' }]}>
                      <Input placeholder="例如：ERROR"/>
                    </Form.Item>
                    <Form.Item name="chk_log_tail_lines" label="检测最近N行" initialValue={200}>
                      <InputNumber min={10} max={5000} style={{ width: '100%' }}/>
                    </Form.Item>
                  </>
                )}

                {CHECK_TYPES.includes(mt) && (
                  <>
                    <Divider orientation="left" plain>告警设置</Divider>
                    <Form.Item name="threshold" label="报警阈值" initialValue={3} tooltip="连续N次检测失败，则发送告警">
                      <Radio.Group>
                        {[1, 2, 3, 4, 5].map(v => <Radio key={v} value={v}>{v}次</Radio>)}
                      </Radio.Group>
                    </Form.Item>
                    <Form.Item name="notify_grp" label="报警联系组" valuePropName="targetKeys"
                      extra={<>去创建 <Link to="/alarm/contact">报警联系人</Link> 和 <Link to="/alarm/group">联系人组</Link>。</>}>
                      <Transfer
                        lazy={false}
                        rowKey={item => item.id}
                        titles={['未选择', '已选择']}
                        listStyle={{ width: 260, height: 200 }}
                        dataSource={groupStore.records}
                        render={item => item.name}/>
                    </Form.Item>
                    <Form.Item name="notify_mode" label="报警方式">
                      <Checkbox.Group options={NOTIFY_MODE_OPTIONS}/>
                    </Form.Item>
                    <Form.Item name="quiet" label="告警静默期" initialValue={24 * 60} extra="相同的告警信息，静默期内只发送一次，避免刷屏">
                      <Select style={{ width: '100%' }}>
                        <Select.Option value={5}>5分钟</Select.Option>
                        <Select.Option value={10}>10分钟</Select.Option>
                        <Select.Option value={15}>15分钟</Select.Option>
                        <Select.Option value={30}>30分钟</Select.Option>
                        <Select.Option value={60}>60分钟</Select.Option>
                        <Select.Option value={3 * 60}>3小时</Select.Option>
                        <Select.Option value={6 * 60}>6小时</Select.Option>
                        <Select.Option value={12 * 60}>12小时</Select.Option>
                        <Select.Option value={24 * 60}>24小时</Select.Option>
                      </Select>
                    </Form.Item>
                  </>
                )}
              </>
            )
          }}
        </Form.Item>

        <Form.Item name="rate" label="检测/采集周期(秒)" initialValue={60} rules={[{ required: true }]}>
          <InputNumber min={10} style={{ width: '100%' }}/>
        </Form.Item>
        <Form.Item name="desc" label="备注">
          <Input.TextArea rows={2}/>
        </Form.Item>
        <Button icon={<ThunderboltOutlined/>} loading={testing} onClick={handleTest}>测试连通性/可用性</Button>
      </Form>
      {showTmp && <TemplateSelector onOk={({ body }) => { record.extra = body; form.setFieldsValue({ extra: body }) }} onCancel={() => setShowTmp(false)}/>}
    </Modal>
  )
}
