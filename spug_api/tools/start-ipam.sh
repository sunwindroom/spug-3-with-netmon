#!/bin/bash
# Copyright: (c) OpenSpug Organization. https://github.com/openspug/spug
# Copyright: (c) <spug.dev@gmail.com>
# Released under the AGPL-3.0 License.
# start ipam (IP address management) background service

cd $(dirname $(dirname $0))
if [ -f ./venv/bin/activate ]; then
  source ./venv/bin/activate
fi

if command -v python3 &> /dev/null; then
  PYTHON=python3
else
  PYTHON=python
fi

exec $PYTHON manage.py runipam
