#!/bin/bash
#
set -e

if [ -e /root/.bashrc ]; then
    source /root/.bashrc
fi

if [ ! -d /data/spug/spug_api/apps ]; then
    cp -a /opt/spug_src/spug_api /data/spug/spug_api
    cp -a /opt/spug_src/spug_web /data/spug/spug_web
fi

mkdir -p /data/spug/spug_api/logs

if [ ! -f /data/spug/spug_api/spug/overrides.py ]; then
    SECRET_KEY=$(< /dev/urandom tr -dc '!@#%^.a-zA-Z0-9' | head -c50)
    cat > /data/spug/spug_api/spug/overrides.py << EOF
import os


DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1']
SECRET_KEY = '${SECRET_KEY}'

DATABASES = {
    'default': {
        'ATOMIC_REQUESTS': True,
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('MYSQL_DATABASE'),
        'USER': os.environ.get('MYSQL_USER'),
        'PASSWORD': os.environ.get('MYSQL_PASSWORD'),
        'HOST': os.environ.get('MYSQL_HOST'),
        'PORT': os.environ.get('MYSQL_PORT'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'sql_mode': 'STRICT_TRANS_TABLES',
        }
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://:Redis2024Secure@127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis://127.0.0.1:6379/2')],
        },
    },
}
EOF
fi

exec supervisord -c /etc/supervisord.conf
