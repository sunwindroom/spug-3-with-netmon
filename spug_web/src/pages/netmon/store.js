/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import { observable } from 'mobx';
import { http } from 'libs';

class Store {
  autoReload = null;

  // 总览大屏
  @observable overview = {};
  @observable ovFetching = false;

  // 拓扑
  @observable topology = { nodes: [], edges: [] };
  @observable topoFetching = false;

  // 资源台账
  @observable groups = [];
  @observable devices = [];
  @observable devFetching = false;
  @observable device = {};
  @observable formVisible = false;
  @observable detailVisible = false;

  // 异常事件
  @observable anomalies = [];
  @observable anomalyFetching = false;

  // 自动发现
  @observable discoveryTaskId = null;
  @observable discoveryResult = { status: 'idle', results: [] };
  @observable discoveryPolling = null;

  // 报表
  @observable reports = [];
  @observable reportRecords = [];
  @observable reportFetching = false;
  @observable reportFormVisible = false;
  @observable report = {};

  // 告警规则
  @observable alertRules = [];
  @observable alertRuleFetching = false;
  @observable alertRuleFormVisible = false;
  @observable alertRule = {};

  // 维护窗口
  @observable maintenanceWindows = [];
  @observable mwFetching = false;
  @observable mwFormVisible = false;
  @observable maintenanceWindow = {};

  // 自动化处置
  @observable remediationActions = [];
  @observable remediationFetching = false;
  @observable remediationFormVisible = false;
  @observable remediationAction = {};
  @observable remediationLogs = [];

  fetchOverview = () => {
    if (this.autoReload === false) return;
    this.ovFetching = true;
    return http.get('/api/netmon/overview/')
      .then(res => this.overview = res)
      .finally(() => {
        this.ovFetching = false;
        if (this.autoReload) setTimeout(this.fetchOverview, 10000)
      })
  };

  fetchTopology = (group_id) => {
    this.topoFetching = true;
    return http.get('/api/netmon/topology/', { params: { group_id } })
      .then(res => this.topology = res)
      .finally(() => this.topoFetching = false)
  };

  fetchGroups = () => {
    return http.get('/api/netmon/group/').then(res => this.groups = res)
  };

  fetchDevices = (group_id) => {
    this.devFetching = true;
    return http.get('/api/netmon/device/', { params: { group_id } })
      .then(res => this.devices = res)
      .finally(() => this.devFetching = false)
  };

  showForm = (info) => {
    this.device = info ? { ...info } : { category: 'server', monitor_type: 'ping', rate: 60 };
    this.formVisible = true;
  };

  showDetail = (info) => {
    this.device = info;
    this.detailVisible = true;
  };

  fetchMetricHistory = (device_id, metric_key, minutes = 60) => {
    return http.get('/api/netmon/metric/history/', { params: { device_id, metric_key, minutes } })
  };

  fetchAnomalies = (status) => {
    this.anomalyFetching = true;
    return http.get('/api/netmon/anomaly/', { params: { status } })
      .then(res => this.anomalies = res)
      .finally(() => this.anomalyFetching = false)
  };

  ackAnomaly = (id, status) => {
    return http.patch('/api/netmon/anomaly/', { id, status })
  };

  startDiscovery = (cidr) => {
    return http.post('/api/netmon/discovery/start/', { cidr })
      .then(({ task_id }) => {
        this.discoveryTaskId = task_id;
        this.discoveryResult = { status: 'running', results: [] };
        this._pollDiscovery(task_id);
      })
  };

  _pollDiscovery = (task_id) => {
    http.get('/api/netmon/discovery/result/', { params: { task_id } })
      .then(res => {
        this.discoveryResult = res;
        if (res.status === 'running') {
          this.discoveryPolling = setTimeout(() => this._pollDiscovery(task_id), 2000)
        }
      })
  };

  stopDiscoveryPolling = () => {
    if (this.discoveryPolling) clearTimeout(this.discoveryPolling)
  };

  importDiscovery = (items, group_id) => {
    return http.post('/api/netmon/discovery/import/', { items, group_id })
  };

  fetchReports = () => {
    this.reportFetching = true;
    return http.get('/api/netmon/report/')
      .then(res => this.reports = res)
      .finally(() => this.reportFetching = false)
  };

  showReportForm = (info) => {
    this.report = info ? { ...info } : { report_type: 'daily', recipients: [] };
    this.reportFormVisible = true;
  };

  fetchReportRecords = (report_id) => {
    return http.get('/api/netmon/report/record/', { params: { report_id } })
      .then(res => this.reportRecords = res)
  };

  generateReport = (id) => {
    return http.post('/api/netmon/report/generate/', { id })
  };

  downloadReportUrl = (id) => `/api/netmon/report/download/?id=${id}`;

  // ---- 批量操作 / 连通性测试 ----
  batchDeleteDevices = (ids) => http.post('/api/netmon/device/batch-delete/', { ids });

  importDevicesCsv = (file) => {
    const data = new FormData();
    data.append('file', file);
    return http.post('/api/netmon/device/import-csv/', data);
  };

  testConnectivity = (payload) => http.post('/api/netmon/device/test-connectivity/', payload);

  // ---- 告警规则 ----
  fetchAlertRules = () => {
    this.alertRuleFetching = true;
    return http.get('/api/netmon/alert-rule/')
      .then(res => this.alertRules = res)
      .finally(() => this.alertRuleFetching = false)
  };

  showAlertRuleForm = (info) => {
    this.alertRule = info ? { ...info } : { operator: '>', level: 'warning', consecutive_times: 1, notify_grp: [] };
    this.alertRuleFormVisible = true;
  };

  // ---- 维护窗口 ----
  fetchMaintenanceWindows = () => {
    this.mwFetching = true;
    return http.get('/api/netmon/maintenance-window/')
      .then(res => this.maintenanceWindows = res)
      .finally(() => this.mwFetching = false)
  };

  showMaintenanceForm = (info) => {
    this.maintenanceWindow = info ? { ...info } : {};
    this.mwFormVisible = true;
  };

  // ---- 自动化处置 ----
  fetchRemediationActions = () => {
    this.remediationFetching = true;
    return http.get('/api/netmon/remediation-action/')
      .then(res => this.remediationActions = res)
      .finally(() => this.remediationFetching = false)
  };

  showRemediationForm = (info) => {
    this.remediationAction = info ? { ...info } : { level: 'critical', cooldown_minutes: 15 };
    this.remediationFormVisible = true;
  };

  fetchRemediationLogs = () => http.get('/api/netmon/remediation-log/').then(res => this.remediationLogs = res);
}

export default new Store()
