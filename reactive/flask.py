import os
import shutil
from charmhelpers.core import hookenv
from charmhelpers.core.hookenv import (
    status_set,
    open_port,
    config,
)
from charmhelpers.contrib.python.packages import pip_install
from charms.reactive import when, when_not, set_state, remove_state
from charms.layer.nginx import configure_site
from charms.layer.flaskhelpers import restart_api, set_workers
from subprocess import call

config = hookenv.config()

@when_not('flask.installed')
def install():
    if not os.path.exists("/home/ubuntu/flask"):
        os.mkdir('/home/ubuntu/flask')
        shutil.chown('/home/ubuntu/flask', user='ubuntu', group='ubuntu')
        touch('/home/ubuntu/flask/flask-config')
    for pkg in ['Flask', 'gunicorn', 'nginx']:
        pip_install(pkg)
    set_state('flask.installed')
    if config["nginx"]:
        set_state('nginx.install')
    else:    
        set_state('nginx.stop')

@when('nginx.stop', 'nginx.available')
def stop_nginx():
    call(['service', 'nginx', 'stop'])
    remove_state('nginx.stop')

def start_nginx_sevice():
    call(['service', 'nginx', 'start'])

@when('nginx.available', 'nginx.install')
@when_not('flask.nginx.installed')
def start_nginx():
    hookenv.log("Configuring site for nginx")
    configure_site('flask', 'gunicornhost.conf', flask_port=config['flask-port'])
    set_state('flask.nginx.installed')

@when('config.changed.nginx')
def config_changed_nginx():
    if config["nginx"]:
        start_nginx_sevice()
        set_state('nginx.install')
        restart_api(config['flask-port'])
    else:
        stop_nginx()
        remove_state('nginx.install')
        remove_state('flask.nginx.installed')
        restart_api(config['flask-port'])


@when('config.changed.flask-port', 'flask.installed')
def config_changed_flask_port():
    if config.changed('flask-port') and config["nginx"]:
        hookenv.log("Port change detected")
        hookenv.log("Restarting API")
        remove_state('flask.nginx.installed')
        restart_api(config['flask-port'])

@when('config.changed.workers', 'flask.installed')
def config_changed_workers():
    if config.changed('workers') and config["nginx"]:
        hookenv.log('Workers change detected')
        hookenv.log("Restarting API")
        set_workers()

def touch(path):
    with open(path, 'a'):
        os.utime(path, None)