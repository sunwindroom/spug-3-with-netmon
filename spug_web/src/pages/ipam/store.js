/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import { observable } from 'mobx';
import { http } from 'libs';

class Store {
  @observable activeTab = 'overview';
  @observable subnets = [];
  @observable subnetFetching = false;
  @observable subnetFormVisible = false;
  @observable subnet = {};

  @observable addresses = [];
  @observable addressFetching = false;
  @observable allocateFormVisible = false;
  @observable activeSubnetId = null;

  @observable insights = [];
  @observable insightsFetching = false;

  @observable securityEvents = [];
  @observable securityFetching = false;

  @observable changeLogs = [];
  @observable logFetching = false;

  @observable isolationTemplates = [];
  @observable templateFetching = false;
  @observable templateFormVisible = false;
  @observable isolationTemplate = {};

  fetchSubnets = () => {
    this.subnetFetching = true;
    return http.get('/api/ipam/subnet/')
      .then(res => this.subnets = res)
      .finally(() => this.subnetFetching = false)
  };

  showSubnetForm = (info) => {
    this.subnet = info ? { ...info } : { warning_threshold: 80, auto_isolate_unauthorized: false };
    this.subnetFormVisible = true;
  };

  fetchAddresses = (subnetId) => {
    this.activeSubnetId = subnetId;
    this.addressFetching = true;
    return http.get(`/api/ipam/subnet/${subnetId}/addresses/`)
      .then(res => this.addresses = res)
      .finally(() => this.addressFetching = false)
  };

  allocate = (data) => http.post('/api/ipam/address/allocate/', data);
  reserve = (data) => http.post('/api/ipam/address/reserve/', data);
  release = (id, remark) => http.post('/api/ipam/address/release/', { id, remark });
  updateAddress = (data) => http.post('/api/ipam/address/update/', data);
  isolate = (id, remark) => http.post('/api/ipam/address/isolate/', { id, remark });
  restore = (id, remark) => http.post('/api/ipam/address/restore/', { id, remark });

  @observable scanResults = [];
  @observable scanFindings = [];
<<<<<<< HEAD
  @observable activeScanSubnetId = null;
  @observable scanSubnetName = '';
=======
  @observable scanResultVisible = false;
  @observable activeScanSubnetId = null;
>>>>>>> 115dece1e337a145b76b2c9fee198c5e29bd2aee

  startScan = (subnetId) => http.post('/api/ipam/scan/start/', { subnet_id: subnetId });

  importDiscovery = (subnetId, devices) => http.post('/api/ipam/scan/import/', { subnet_id: subnetId, devices });

<<<<<<< HEAD
  showScanResult = (subnetId, subnetName, results, findings) => {
    this.activeScanSubnetId = subnetId;
    this.scanSubnetName = subnetName;
    this.scanResults = results || [];
    this.scanFindings = findings || [];
    this.activeTab = 'scanResult';
  };

  clearScanResult = () => {
    this.scanResults = [];
    this.scanFindings = [];
    this.activeScanSubnetId = null;
    this.scanSubnetName = '';
=======
  showScanResult = (subnetId, results, findings) => {
    this.activeScanSubnetId = subnetId;
    this.scanResults = results || [];
    this.scanFindings = findings || [];
    this.scanResultVisible = true;
>>>>>>> 115dece1e337a145b76b2c9fee198c5e29bd2aee
  };

  fetchInsights = () => {
    this.insightsFetching = true;
    return http.get('/api/ipam/insights/')
      .then(res => this.insights = res)
      .finally(() => this.insightsFetching = false)
  };

  fetchSecurityEvents = () => {
    this.securityFetching = true;
    return http.get('/api/ipam/security-events/')
      .then(res => this.securityEvents = res)
      .finally(() => this.securityFetching = false)
  };

  fetchChangeLogs = (params) => {
    this.logFetching = true;
    return http.get('/api/ipam/change-log/', { params })
      .then(res => this.changeLogs = res)
      .finally(() => this.logFetching = false)
  };

  fetchIsolationTemplates = () => {
    this.templateFetching = true;
    return http.get('/api/ipam/isolation-template/')
      .then(res => this.isolationTemplates = res)
      .finally(() => this.templateFetching = false)
  };

  showTemplateForm = (info) => {
    this.isolationTemplate = info ? { ...info } : { is_default: false };
    this.templateFormVisible = true;
  };
}

export default new Store()
