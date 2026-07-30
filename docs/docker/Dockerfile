FROM centos:7.9.2009

ENV TZ=Asia/Shanghai
RUN sed -i 's|^mirrorlist=|#mirrorlist=|g' /etc/yum.repos.d/CentOS-*.repo && sed -i 's|^#baseurl=http://mirror.centos.org/centos|baseurl=https://mirrors.aliyun.com/centos|g' /etc/yum.repos.d/CentOS-*.repo
RUN yum install -y epel-release && sed -i 's|^mirrorlist=|#mirrorlist=|g' /etc/yum.repos.d/epel*.repo && sed -i 's|^#baseurl=http://download.fedoraproject.org/pub/epel|baseurl=https://mirrors.aliyun.com/epel|g' /etc/yum.repos.d/epel*.repo
RUN yum install -y --setopt=tsflags=nodocs nginx redis mariadb-devel python36 python36-devel openldap-devel supervisor git gcc wget unzip net-tools sshpass rsync sshfs && yum -y clean all --enablerepo='*'

RUN pip3 install --no-cache-dir --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
RUN pip3 install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
    gunicorn \
    mysqlclient \
    cryptography==36.0.2 \
    apscheduler==3.7.0 \
    asgiref==3.2.10 \
    Django==2.2.28 \
    channels==2.3.1 \
    channels_redis==2.4.1 \
    paramiko==2.11.0 \
    django-redis==4.10.0 \
    requests==2.27.1 \
    GitPython==3.1.20 \
    python-ldap==3.4.0 \
    openpyxl==3.0.3 \
    user_agents==2.2.0 \
    pysnmp==4.4.12 \
    pysnmp-mibs==0.1.6

RUN curl -fsSL https://rpm.nodesource.com/setup_16.x | bash - && yum install -y nodejs && yum -y clean all

RUN localedef -c -i en_US -f UTF-8 en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
RUN echo -e '\n# Source definitions\n. /etc/profile\n' >> /root/.bashrc
RUN mkdir -p /data/repos /data/spug/spug_api /data/spug/spug_web /opt/spug_src

COPY init_spug /usr/bin/
COPY nginx.conf /etc/nginx/
COPY ssh_config /etc/ssh/
COPY spug.ini /etc/supervisord.d/
COPY redis.conf /etc/
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

COPY spug_api /opt/spug_src/spug_api
COPY spug_web /opt/spug_src/spug_web

RUN npm config set registry https://registry.npmmirror.com && cd /opt/spug_src/spug_web && npm install --legacy-peer-deps && npx react-app-rewired build

VOLUME /data
EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
