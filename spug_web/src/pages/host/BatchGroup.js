/**
 * Copyright (c) OpenSpug Organization. https://github.com/openspug/spug
 * Copyright (c) <spug.dev@gmail.com>
 * Released under the AGPL-3.0 License.
 */
import React, { useState, useEffect } from 'react';
import { observer } from 'mobx-react';
import { Modal, Tree, Spin, Alert } from 'antd';
import { FolderOpenOutlined, FolderOutlined } from '@ant-design/icons';
import store from './store';
import lds from 'lodash';

function BatchGroup() {
  const [loading, setLoading] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState([]);
  const [expands, setExpands] = useState([]);

  useEffect(() => {
    if (store.batchGroupVisible) {
      setSelectedKeys([]);
      const tmp = store.treeData.filter(x => x.children.length);
      setExpands(tmp.map(x => x.key));
    }
  }, [store.batchGroupVisible])

  function handleSubmit() {
    setLoading(true);
    store.batchUpdateGroup(selectedKeys)
      .finally(() => setLoading(false))
  }

  function handleExpand(keys) {
    setExpands(keys)
  }

  function treeRender(nodeData) {
    const length = store.counter[nodeData.key]?.size
    return (
      <div style={{display: 'flex', alignItems: 'center'}}>
        {expands.includes(nodeData.key) ? <FolderOpenOutlined/> : <FolderOutlined/>}
        <div style={{marginLeft: 6}}>{nodeData.title}</div>
        {length ? <div style={{marginLeft: 8, color: '#999', fontSize: 12}}>({length})</div> : null}
      </div>
    )
  }

  return (
    <Modal
      visible={store.batchGroupVisible}
      width={600}
      title={`批量调整分组（已选择 ${store.selectedRowKeys.length} 台主机）`}
      onOk={handleSubmit}
      okButtonProps={{disabled: selectedKeys.length === 0}}
      confirmLoading={loading}
      onCancel={() => store.batchGroupVisible = false}>
      <Alert
        type="info"
        showIcon
        style={{marginBottom: 16}}
        message="选择目标分组后，所选主机的分组将被替换为选择的分组。"
      />
      <Spin spinning={store.grpFetching}>
        <Tree
          checkable
          autoExpandParent
          expandedKeys={expands}
          selectedKeys={[]}
          checkedKeys={selectedKeys}
          treeData={store.treeData}
          titleRender={treeRender}
          onExpand={handleExpand}
          onCheck={(keys) => setSelectedKeys(keys)}
        />
      </Spin>
    </Modal>
  )
}

export default observer(BatchGroup)