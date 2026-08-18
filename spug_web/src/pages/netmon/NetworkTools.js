import React, {useState} from 'react';
import {Card, Form, Input, Button, Tabs, Tag, Alert, InputNumber, Select, Typography} from 'antd';
import {PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined} from '@ant-design/icons';
import {http} from 'libs';

const {TextArea} = Input;
const {Text, Paragraph} = Typography;

function PingTool() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form] = Form.useForm();

  function handleRun() {
    form.validateFields().then(values => {
      setLoading(true);
      setResult(null);
      http.post('/api/netmon/tools/ping/', values).then(res => {
        setResult(res);
      }).finally(() => setLoading(false));
    });
  }

  return (
    <div>
      <Form form={form} layout="inline" initialValues={{count: 4}}>
        <Form.Item name="target" rules={[{required: true, message: '请输入目标地址'}]}>
          <Input placeholder="IP或域名，如 8.8.8.8" style={{width: 240}}/>
        </Form.Item>
        <Form.Item name="count" label="次数">
          <InputNumber min={1} max={20} style={{width: 80}}/>
        </Form.Item>
        <Form.Item>
          <Button type="primary" icon={<PlayCircleOutlined/>} loading={loading} onClick={handleRun}>执行</Button>
        </Form.Item>
      </Form>
      {result && (
        <Card size="small" style={{marginTop: 16}}>
          <div style={{marginBottom: 8}}>
            {result.exit_code === 0 ?
              <Tag icon={<CheckCircleOutlined/>} color="success">Ping 通</Tag> :
              <Tag icon={<CloseCircleOutlined/>} color="error">Ping 失败</Tag>
            }
          </div>
          <pre style={{maxHeight: 400, overflow: 'auto', fontSize: 13, lineHeight: 1.6}}>{result.output}</pre>
        </Card>
      )}
    </div>
  );
}

function TracerouteTool() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form] = Form.useForm();

  function handleRun() {
    form.validateFields().then(values => {
      setLoading(true);
      setResult(null);
      http.post('/api/netmon/tools/traceroute/', values).then(res => {
        setResult(res);
      }).finally(() => setLoading(false));
    });
  }

  return (
    <div>
      <Form form={form} layout="inline" initialValues={{max_hops: 30}}>
        <Form.Item name="target" rules={[{required: true, message: '请输入目标地址'}]}>
          <Input placeholder="IP或域名，如 8.8.8.8" style={{width: 240}}/>
        </Form.Item>
        <Form.Item name="max_hops" label="最大跳数">
          <InputNumber min={1} max={50} style={{width: 80}}/>
        </Form.Item>
        <Form.Item>
          <Button type="primary" icon={<PlayCircleOutlined/>} loading={loading} onClick={handleRun}>执行</Button>
        </Form.Item>
      </Form>
      {result && (
        <Card size="small" style={{marginTop: 16}}>
          <pre style={{maxHeight: 400, overflow: 'auto', fontSize: 13, lineHeight: 1.6}}>{result.output}</pre>
        </Card>
      )}
    </div>
  );
}

function PortTestTool() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form] = Form.useForm();

  function handleRun() {
    form.validateFields().then(values => {
      setLoading(true);
      setResult(null);
      http.post('/api/netmon/tools/port-test/', values).then(res => {
        setResult(res);
      }).finally(() => setLoading(false));
    });
  }

  return (
    <div>
      <Form form={form} layout="inline" initialValues={{timeout: 3}}>
        <Form.Item name="host" rules={[{required: true, message: '请输入主机地址'}]}>
          <Input placeholder="IP或域名" style={{width: 200}}/>
        </Form.Item>
        <Form.Item name="port" rules={[{required: true, message: '请输入端口'}]}>
          <InputNumber min={1} max={65535} placeholder="端口" style={{width: 100}}/>
        </Form.Item>
        <Form.Item name="timeout" label="超时(s)">
          <InputNumber min={1} max={10} step={0.5} style={{width: 80}}/>
        </Form.Item>
        <Form.Item>
          <Button type="primary" icon={<PlayCircleOutlined/>} loading={loading} onClick={handleRun}>测试</Button>
        </Form.Item>
      </Form>
      {result && (
        <Card size="small" style={{marginTop: 16}}>
          {result.reachable ?
            <Alert type="success" showIcon icon={<CheckCircleOutlined/>} message={result.message}/> :
            <Alert type="error" showIcon icon={<CloseCircleOutlined/>} message={result.message}/>
          }
        </Card>
      )}
    </div>
  );
}

function DnsLookupTool() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [form] = Form.useForm();

  function handleRun() {
    form.validateFields().then(values => {
      setLoading(true);
      setResult(null);
      http.post('/api/netmon/tools/dns-lookup/', values).then(res => {
        setResult(res);
      }).finally(() => setLoading(false));
    });
  }

  return (
    <div>
      <Form form={form} layout="inline" initialValues={{record_type: 'A'}}>
        <Form.Item name="domain" rules={[{required: true, message: '请输入域名'}]}>
          <Input placeholder="域名，如 www.example.com" style={{width: 240}}/>
        </Form.Item>
        <Form.Item name="record_type" label="记录类型">
          <Select style={{width: 100}} options={[
            {value: 'A', label: 'A'},
            {value: 'AAAA', label: 'AAAA'},
            {value: 'MX', label: 'MX'},
            {value: 'NS', label: 'NS'},
            {value: 'TXT', label: 'TXT'},
            {value: 'CNAME', label: 'CNAME'},
          ]}/>
        </Form.Item>
        <Form.Item>
          <Button type="primary" icon={<PlayCircleOutlined/>} loading={loading} onClick={handleRun}>查询</Button>
        </Form.Item>
      </Form>
      {result && (
        <Card size="small" style={{marginTop: 16}}>
          {result.records && result.records.length > 0 && (
            <div style={{marginBottom: 8}}>
              {result.records.map((r, i) => <Tag key={i} color="blue">{r}</Tag>)}
            </div>
          )}
          <pre style={{maxHeight: 300, overflow: 'auto', fontSize: 13, lineHeight: 1.6}}>{result.output}</pre>
        </Card>
      )}
    </div>
  );
}

export default function NetworkTools() {
  return (
    <Card title="网络工具箱" bodyStyle={{minHeight: 400}}>
      <Tabs defaultActiveKey="ping">
        <Tabs.TabPane tab="Ping 探测" key="ping"><PingTool/></Tabs.TabPane>
        <Tabs.TabPane tab="路由追踪" key="traceroute"><TracerouteTool/></Tabs.TabPane>
        <Tabs.TabPane tab="端口连通性" key="port"><PortTestTool/></Tabs.TabPane>
        <Tabs.TabPane tab="DNS 查询" key="dns"><DnsLookupTool/></Tabs.TabPane>
      </Tabs>
    </Card>
  );
}