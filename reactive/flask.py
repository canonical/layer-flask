import os
import shutil
from subprocess import call

from charmhelpers.core import hookenv
from charms.layer.flaskhelpers import restart_api, set_workers
from charms.layer.nginx import configure_site
from charms.reactive import remove_state, set_state, when, when_not

cfg = hookenv.config()


@when_not("flask.installed")
def install():
    if not os.path.exists("/home/ubuntu/flask"):
        os.mkdir("/home/ubuntu/flask")
        shutil.chown("/home/ubuntu/flask", user="ubuntu", group="ubuntu")
        touch("/home/ubuntu/flask/flask-config")
    set_state("flask.installed")
    if cfg["nginx"]:
        set_state("nginx.install")
    else:
        set_state("nginx.stop")


@when("nginx.stop", "nginx.available")
def stop_nginx():
    call(["service", "nginx", "stop"])
    remove_state("nginx.stop")


def start_nginx_sevice():
    call(["service", "nginx", "start"])


@when("nginx.available", "nginx.install")
@when_not("flask.nginx.installed")
def start_nginx():
    hookenv.log("Configuring site for nginx")
    configure_site("flask", "gunicornhost.conf", flask_port=cfg["flask-port"])
    set_state("flask.nginx.installed")


@when("cfg.changed.nginx")
def config_changed_nginx():
    if cfg["nginx"]:
        start_nginx_sevice()
        set_state("nginx.install")
        restart_api(cfg["flask-port"])
    else:
        stop_nginx()
        remove_state("nginx.install")
        remove_state("flask.nginx.installed")
        restart_api(cfg["flask-port"])


@when("cfg.changed.flask-port", "flask.installed")
def config_changed_flask_port():
    if cfg.changed("flask-port") and cfg["nginx"]:
        hookenv.log("Port change detected")
        hookenv.log("Restarting API")
        remove_state("flask.nginx.installed")
        restart_api(cfg["flask-port"])


@when("cfg.changed.workers", "flask.installed")
def config_changed_workers():
    if cfg.changed("workers") and cfg["nginx"]:
        hookenv.log("Workers change detected")
        hookenv.log("Restarting API")
        set_workers()


def touch(path):
    with open(path, "a"):
        os.utime(path, None)
