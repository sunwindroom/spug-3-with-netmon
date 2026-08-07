/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useEffect } from 'react';
import { Tabs } from 'antd';
import { AuthDiv, Breadcrumb } from 'components';
import Overview from './Overview';
import Topology from './Topology';
import Devices from './Devices';
import Discovery from './Discovery';
import Reports from './Reports';
import MaintenanceWindows from './MaintenanceWindows';
import Remediation from './Remediation';
import DeviceDetail from './DeviceDetail';
import store from './store';

export default function NetmonIndex() {
  useEffect(() => {
    store.fetchGroups();
    store.fetchDevices();
    return () => { store.stopDiscoveryPolling(); store.stopOverviewPolling(); }
  }, []);

  return (
    <AuthDiv auth="netmon.device.view">
      <Breadcrumb>
        <Breadcrumb.Item>首页</Breadcrumb.Item>
        <Breadcrumb.Item>IT资源监控</Breadcrumb.Item>
      </Breadcrumb>
      <Tabs defaultActiveKey="overview" type="card">
        <Tabs.TabPane tab="实时总览" key="overview"><Overview/></Tabs.TabPane>
        <Tabs.TabPane tab="拓扑视图" key="topology"><Topology/></Tabs.TabPane>
        <Tabs.TabPane tab="资源台账" key="devices"><Devices/></Tabs.TabPane>
        <Tabs.TabPane tab="维护窗口" key="maintenance"><MaintenanceWindows/></Tabs.TabPane>
        <Tabs.TabPane tab="自动化处置" key="remediation"><Remediation/></Tabs.TabPane>
        <Tabs.TabPane tab="自动发现" key="discovery"><Discovery/></Tabs.TabPane>
        <Tabs.TabPane tab="报表管理" key="reports"><Reports/></Tabs.TabPane>
      </Tabs>
      <DeviceDetail/>
    </AuthDiv>
  )
}
