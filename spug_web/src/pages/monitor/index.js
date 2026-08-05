/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Released under the AGPL-3.0 License.
 */
import React from 'react';
import { observer } from 'mobx-react';
import { Tabs } from 'antd';
import { AuthDiv, Breadcrumb } from 'components';
import Overview from '../netmon/Overview';
import ComTable from './Table';
import ComForm from './Form';
import MonitorCard from './MonitorCard';
import store from './store';

export default observer(function () {
  return (
    <AuthDiv auth="monitor.monitor.view">
      <Breadcrumb>
        <Breadcrumb.Item>首页</Breadcrumb.Item>
        <Breadcrumb.Item>监控中心</Breadcrumb.Item>
      </Breadcrumb>
      <Tabs defaultActiveKey="dashboard" type="card">
        <Tabs.TabPane tab="总览大屏" key="dashboard">
          <Overview/>
        </Tabs.TabPane>
        <Tabs.TabPane tab="监控任务" key="tasks">
          <MonitorCard/>
          <ComTable/>
        </Tabs.TabPane>
      </Tabs>
      {store.formVisible && <ComForm/>}
    </AuthDiv>
  )
})
