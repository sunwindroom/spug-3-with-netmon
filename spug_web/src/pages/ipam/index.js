/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect } from 'react';
import { observer } from 'mobx-react';
import { Tabs } from 'antd';
import { AuthDiv, Breadcrumb } from 'components';
import Overview from './Overview';
import Subnets from './Subnets';
import ScanResult from './ScanResult';
import Addresses from './Addresses';
import SecurityEvents from './SecurityEvents';
import IsolationTemplates from './IsolationTemplates';
import AuditLog from './AuditLog';
import store from './store';

export default observer(function IpamIndex() {
  useEffect(() => {
    store.fetchSubnets();
  }, []);

  return (
    <AuthDiv auth="ipam.subnet.view">
      <Breadcrumb>
        <Breadcrumb.Item>首页</Breadcrumb.Item>
        <Breadcrumb.Item>IP地址管理</Breadcrumb.Item>
      </Breadcrumb>
      <Tabs activeKey={store.activeTab} onChange={key => store.activeTab = key} type="card">
        <Tabs.TabPane tab="预测性洞察" key="overview"><Overview/></Tabs.TabPane>
        <Tabs.TabPane tab="网段管理" key="subnets"><Subnets/></Tabs.TabPane>
        {store.scanResults.length > 0 && <Tabs.TabPane tab={`扫描结果(${store.scanResults.length})`} key="scanResult"><ScanResult/></Tabs.TabPane>}
        <Tabs.TabPane tab="地址分配" key="addresses"><Addresses/></Tabs.TabPane>
        <Tabs.TabPane tab="未授权设备/冲突" key="security"><SecurityEvents/></Tabs.TabPane>
        <Tabs.TabPane tab="隔离处置模板" key="isolation"><IsolationTemplates/></Tabs.TabPane>
        <Tabs.TabPane tab="变更审计" key="audit"><AuditLog/></Tabs.TabPane>
      </Tabs>
    </AuthDiv>
  )
})
