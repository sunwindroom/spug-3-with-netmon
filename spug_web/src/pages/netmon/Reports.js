/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react';
import { Table, Space, Select, Input, Form, Modal, message, Card, Tag, Row, Col } from 'antd';
import { AuthButton, LinkButton } from 'components';
import { http } from 'libs';
import store from './store';

const TYPE_LABEL = { daily: '日报', weekly: '周报', monthly: '月报', manual: '手动/自定义' };

export default observer(function Reports() {
  const [recordVisible, setRecordVisible] = useState(false);
  const [activeReport, setActiveReport] = useState(null);
  const [generating, setGenerating] = useState(null);

  useEffect(() => { store.fetchReports() }, []);

  function handleDelete(record) {
    Modal.confirm({
      title: '删除确认', content: `确定要删除报表【${record.name}】吗？`,
      onOk: () => http.delete('/api/netmon/report/', { params: { id: record.id } })
        .then(() => { message.success('删除成功'); store.fetchReports() })
    })
  }

  function handleGenerate(record) {
    setGenerating(record.id);
    store.generateReport(record.id)
      .then(() => { message.success('报表已生成'); store.fetchReports() })
      .finally(() => setGenerating(null))
  }

  function openRecords(record) {
    setActiveReport(record);
    store.fetchReportRecords(record.id);
    setRecordVisible(true);
  }

  const columns = [
    { title: '报表名称', dataIndex: 'name' },
    { title: '类型', dataIndex: 'report_type_alias', render: (v, r) => <Tag>{v}</Tag> },
    { title: '统计范围', dataIndex: 'group_name' },
    { title: '最近生成时间', dataIndex: 'last_generated_at', render: v => v || '未生成' },
    {
      title: '操作', width: 260, render: (_, r) => (
        <Space>
          <AuthButton auth="netmon.report.edit" type="link" loading={generating === r.id}
                      onClick={() => handleGenerate(r)}>立即生成</AuthButton>
          <LinkButton onClick={() => openRecords(r)}>历史报表</LinkButton>
          <LinkButton onClick={() => store.showReportForm(r)}>编辑</LinkButton>
          <AuthButton auth="netmon.report.del" type="link" danger onClick={() => handleDelete(r)}>删除</AuthButton>
        </Space>
      )
    }
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <AuthButton auth="netmon.report.edit" type="primary" onClick={() => store.showReportForm()}>新建报表</AuthButton>
      </Space>
      <Card>
        <Row style={{ marginBottom: 8, color: '#8c8c8c' }}>
          <Col span={24}>
            日报 / 周报 / 月报可配合 <code>python manage.py gen_netmon_reports</code>（建议加入 crontab 每日执行一次）实现自动统计分析与订阅推送；也可随时点击「立即生成」手动出具报表。
          </Col>
        </Row>
        <Table rowKey="id" loading={store.reportFetching} columns={columns} dataSource={store.reports}/>
      </Card>

      {store.reportFormVisible && <ReportForm/>}

      <Modal
        title={activeReport ? `历史报表 - ${activeReport.name}` : '历史报表'}
        visible={recordVisible} footer={null} width={720}
        onCancel={() => setRecordVisible(false)}
      >
        <Table
          rowKey="id" size="small" dataSource={store.reportRecords}
          columns={[
            { title: '统计周期', render: (_, r) => `${r.period_start} ~ ${r.period_end}` },
            { title: '设备总数', dataIndex: ['summary', 'device_total'] },
            { title: '异常次数', dataIndex: ['summary', 'anomaly_count'] },
            { title: '生成时间', dataIndex: 'created_at' },
            { title: '操作', render: (_, r) => <a href={store.downloadReportUrl(r.id)} target="_blank" rel="noreferrer">下载</a> },
          ]}
        />
      </Modal>
    </div>
  )
})

function ReportForm() {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const record = store.report;

  function handleSubmit() {
    form.validateFields().then(values => {
      setSaving(true);
      http.post('/api/netmon/report/', { ...record, ...values })
        .then(() => { message.success('保存成功'); store.reportFormVisible = false; store.fetchReports() })
        .finally(() => setSaving(false))
    })
  }

  return (
    <Modal
      visible destroyOnClose title={record.id ? '编辑报表' : '新建报表'}
      confirmLoading={saving} onOk={handleSubmit}
      onCancel={() => store.reportFormVisible = false}
    >
      <Form form={form} layout="vertical" initialValues={record}>
        <Form.Item name="name" label="报表名称" rules={[{ required: true, message: '请输入报表名称' }]}>
          <Input placeholder="例如：核心机房设备运行日报"/>
        </Form.Item>
        <Form.Item name="report_type" label="报表周期" rules={[{ required: true }]}>
          <Select>
            {Object.entries(TYPE_LABEL).map(([v, l]) => <Select.Option key={v} value={v}>{l}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="group_id" label="统计范围" help="不选择表示统计全部资源">
          <Select allowClear>
            {store.groups.map(g => <Select.Option key={g.key} value={g.key}>{g.title}</Select.Option>)}
          </Select>
        </Form.Item>
      </Form>
    </Modal>
  )
}
