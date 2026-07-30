/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useState } from 'react';
import { observer } from 'mobx-react';
import { ExclamationCircleOutlined } from '@ant-design/icons';
import { Modal, Form, Input, Select, Button, message } from 'antd';
import TemplateSelector from '../exec/task/TemplateSelector';
import HostSelector from 'pages/host/Selector';
import { LinkButton, ACEditor } from 'components';
import { http, cleanCommand } from 'libs';
import store from './store';
import lds from 'lodash';

const helpMap = {
  '1': '返回HTTP状态码200-399则判定为正常，其他为异常。',
  '4': '脚本执行退出状态码为 0 则判定为正常，其他为异常。',
  '6': '通过 docker inspect 判断容器运行状态，Running 为正常，其他为异常。',
  '7': '对数据库监听端口发起TCP连接，连接成功判定为正常（不校验账号密码）。',
  '8': '检测日志文件最近N行内容中是否出现指定关键字（如 ERROR/Exception），出现则判定为异常。',
}

const DB_PORTS = {
  MySQL: 3306, MariaDB: 3306, Oracle: 1521, PostgreSQL: 5432,
  SQLServer: 1433, Redis: 6379, MongoDB: 27017,
}

export default observer(function () {
  const [loading, setLoading] = useState(false);
  const [showTmp, setShowTmp] = useState(false);

  function handleTest() {
    setLoading(true)
    const formData = lds.pick(store.record, ['type', 'targets', 'extra'])
    http.post('/api/monitor/test/', formData, {timeout: 120000})
      .then(res => {
        if (res.is_success) {
          Modal.success({content: res.message})
        } else {
          Modal.warning({content: res.message})
        }
      })
      .finally(() => setLoading(false))
  }

  function handleChangeType(v) {
    store.record.type = v;
    store.record.targets = [];
    store.record.extra = undefined;
  }

  function handleAddGroup() {
    Modal.confirm({
      icon: <ExclamationCircleOutlined/>,
      title: '添加监控分组',
      content: (
        <Form layout="vertical" style={{marginTop: 24}}>
          <Form.Item required label="监控分组">
            <Input onChange={e => store.record.group = e.target.value}/>

          </Form.Item>
        </Form>
      ),
      onOk: () => {
        if (store.record.group) {
          store.groups.push(store.record.group);
        }
      },
    })
  }

  function canNext() {
    const {type, targets, extra, group} = store.record;
    const is_verify = name && group && targets.length;
    if (['2', '3', '4', '6', '7', '8'].includes(type)) {
      return is_verify && extra
    } else {
      return is_verify
    }
  }

  function toNext() {
    const {type, extra} = store.record;
    if (!Number(extra) > 0) {
      if (type === '1' && extra) return message.error('请输入正确的响应时间')
      if (type === '2' || type === '7') return message.error('请输入正确的端口号')
    }
    store.page += 1;
  }

  function getStyle(t) {
    return t.includes(store.record.type) ? {} : {display: 'none'}
  }

  const {name, desc, type, targets, extra, group} = store.record;
  return (
    <Form labelCol={{span: 6}} wrapperCol={{span: 14}}>
      <Form.Item required label="监控分组" style={{marginBottom: 0}}>
        <Form.Item style={{display: 'inline-block', width: 'calc(75%)', marginRight: 8}}>
          <Select value={group} placeholder="请选择监控分组" onChange={v => store.record.group = v}>
            {store.groups.map(item => (
              <Select.Option value={item} key={item}>{item}</Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item style={{display: 'inline-block', width: 'calc(25%-8px)'}}>
          <Button type="link" onClick={handleAddGroup}>添加分组</Button>
        </Form.Item>
      </Form.Item>
      <Form.Item label="监控类型" tooltip={helpMap[type]}>
        <Select placeholder="请选择监控类型" value={type} onChange={handleChangeType}>
          <Select.Option value="1">站点检测</Select.Option>
          <Select.Option value="2">端口检测</Select.Option>
          <Select.Option value="5">Ping检测</Select.Option>
          <Select.Option value="3">进程检测</Select.Option>
          <Select.Option value="4">自定义脚本</Select.Option>
          <Select.Option value="6">Docker检测</Select.Option>
          <Select.Option value="7">数据库检测</Select.Option>
          <Select.Option value="8">日志监控</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item required label="监控名称">
        <Input value={name} onChange={e => store.record.name = e.target.value} placeholder="请输入监控名称"/>
      </Form.Item>
      <Form.Item required label="监控地址" style={getStyle(['1'])}>
        <Select
          mode="tags"
          value={targets}
          tokenSeparators={[',', ' ']}
          onChange={v => store.record.targets = v}
          placeholder="http(s)://开头，支持多个地址，每输入完成一个后按回车确认"
          notFoundContent={null}/>
      </Form.Item>
      <Form.Item required label="监控地址" style={getStyle(['2', '5', '7'])}>
        <Select
          mode="tags"
          value={targets}
          tokenSeparators={[',', ' ']}
          onChange={v => store.record.targets = v}
          placeholder="IP或域名，支持多个地址，每输入完成一个后按回车确认"
          notFoundContent={null}/>
      </Form.Item>
      <Form.Item required label="监控主机" style={getStyle(['3', '4', '6', '8'])}>
        <HostSelector value={targets} onChange={ids => store.record.targets = ids}/>
      </Form.Item>
      <Form.Item label="响应时间" style={getStyle(['1'])}>
        <Input suffix="ms" value={extra} placeholder="最长响应时间（毫秒），不设置则默认10秒超时"
               onChange={e => store.record.extra = e.target.value}/>
      </Form.Item>
      <Form.Item required label="检测端口" style={getStyle(['2'])}>
        <Input value={extra} placeholder="请输入端口号" onChange={e => store.record.extra = e.target.value}/>
      </Form.Item>
      <Form.Item required label="进程名称" extra="执行 ps -ef 看到的进程名称。" style={getStyle(['3'])}>
        <Input value={extra} placeholder="请输入进程名称" onChange={e => store.record.extra = e.target.value}/>
      </Form.Item>
      <Form.Item required label="容器名称" extra="执行 docker ps 看到的容器名称或ID。" style={getStyle(['6'])}>
        <Input value={extra} placeholder="请输入容器名称" onChange={e => store.record.extra = e.target.value}/>
      </Form.Item>
      <Form.Item required label="数据库类型/端口" style={getStyle(['7'])}>
        <Select
          placeholder="选择常见数据库类型自动填充默认端口（可编辑）"
          onChange={v => store.record.extra = String(DB_PORTS[v])}
          style={{marginBottom: 8}}
        >
          {Object.entries(DB_PORTS).map(([k, v]) => <Select.Option key={k} value={k}>{k}（默认端口 {v}）</Select.Option>)}
        </Select>
        <Input value={extra} placeholder="端口号" onChange={e => store.record.extra = e.target.value}/>
      </Form.Item>
      <Form.Item required label="日志路径" style={getStyle(['8'])}>
        <Input
          value={(extra || '').split('||')[0] || ''}
          placeholder="例如：/var/log/nginx/error.log"
          onChange={e => store.record.extra = `${e.target.value}||${(extra || '').split('||')[1] || ''}`}/>
      </Form.Item>
      <Form.Item required label="告警关键字" extra="检测日志最近200行中是否出现该关键字（如 ERROR、Exception），出现即判定为异常。" style={getStyle(['8'])}>
        <Input
          value={(extra || '').split('||')[1] || ''}
          placeholder="例如：ERROR"
          onChange={e => store.record.extra = `${(extra || '').split('||')[0] || ''}||${e.target.value}`}/>
      </Form.Item>
      <Form.Item
        required
        label="脚本内容"
        style={getStyle(['4'])}
        extra={<LinkButton onClick={() => setShowTmp(true)}>从模板添加</LinkButton>}>
        <ACEditor
          mode="sh"
          value={extra || ''}
          width="100%"
          height="200px"
          onChange={e => store.record.extra = cleanCommand(e)}/>
      </Form.Item>
      <Form.Item label="备注信息">
        <Input.TextArea value={desc} onChange={e => store.record.desc = e.target.value} placeholder="请输入备注信息"/>
      </Form.Item>

      <Form.Item wrapperCol={{span: 14, offset: 6}} style={{marginTop: 12}}>
        <Button disabled={!canNext()} type="primary" onClick={toNext}>下一步</Button>
        <Button disabled={!canNext()} type="link" loading={loading} onClick={handleTest}>执行测试</Button>
        <span style={{color: '#888', fontSize: 12}}>Tips: 仅测试第一个监控地址</span>
      </Form.Item>
      {showTmp && <TemplateSelector onOk={({body}) => store.record.extra = body} onCancel={() => setShowTmp(false)}/>}
    </Form>
  )
})