import os
from subprocess import Popen, call

import toml
from charmhelpers.core import hookenv, host
from charmhelpers.core.templating import render
from charms.reactive import set_state

cfg = hookenv.config()


def install_dependencies(pathWheelhouse, pathRequirements):
    hookenv.log("Installing dependencies")
    call(
        [
            "pip",
            "install",
            "--no-index",
            "--find-links=" + pathWheelhouse,
            "-r",
            pathRequirements,
        ]
    )


def install_requirements(pathRequirements):
    hookenv.log("Installing dependencies")
    call(["pip", "install", "--upgrade", "-r", pathRequirements])


# Should be used by the layer including the flask layer
def start_api(path, app, port, template="unitfile", context=None):
    if not context:
        context = {}
    if os.path.exists("/home/ubuntu/flask/flask-config"):
        file = open("/home/ubuntu/flask/flask-config", "w")
        file.write(path + " " + app + " " + template)
        file.close()
        start(path, app, port, template, context)


# Used by the flask layer to restart when flask-port changes occur
def restart_api(port):
    path, app, template = get_app_info()
    if path != "" and app != "" and template != "":
        start(path, app, port, template, {})


def start(path, app, port, template, context):
    if cfg["nginx"]:
        start_api_gunicorn(path, app, port, cfg["workers"], template, context)
    else:
        path = path.rstrip("/")
        Popen(["python3", path])
        set_state("flask.running")


def start_api_gunicorn(path, app, port, workers, template, context):
    stop_api()
    path = path.rstrip("/")
    # info[0] = path to project
    # info[1] = main
    info = path.rsplit("/", 1)
    # remove .py from main
    main = info[1].split(".", 1)[0]
    if os.path.exists(info[0] + "/wsgi.py"):
        os.remove(info[0] + "/wsgi.py")
    render(
        source="gunicorn.wsgi",
        target=info[0] + "/wsgi.py",
        context={"app": app, "main": main},
    )
    unitfile_dict = load_unitfile()
    unitfile_context = {**unitfile_dict, **context}
    unitfile_context['port'] = str(port)
    unitfile_context['pythonpath'] = info[0]
    unitfile_context['app'] = app 
    unitfile_context['workers'] = str(workers) 
    unitfile_context['gunicornpath'] = os.path.join(os.path.dirname(os.getcwd()), ".venv/bin/gunicorn")

    render(source=template,
           target='/etc/systemd/system/flask.service',
           context=unitfile_context)


def is_flask_running():
    if call(["systemctl", "is-active", "flask"]) == 0:
        return True
    return False


def stop_api():
    if host.service_running("flask"):
        host.service_stop("flask")
        call(["systemctl", "disable", "flask"])
        if os.path.exists("/etc/systemd/system/flask.service"):
            os.remove("/etc/systemd/system/flask.service")


def set_workers():
    n_workers = cfg["workers"]
    previous_workers = cfg.previous("workers")
    if os.path.exists("/home/ubuntu/flask/master.pid"):
        file = open("/home/ubuntu/flask/master.pid", "r")
        pid = file.readline().strip()
        file.close()
        if is_flask_running():
            if n_workers > previous_workers:
                while previous_workers < n_workers:
                    call(["kill", "-TTIN", pid])
                    previous_workers += 1
            elif n_workers < previous_workers:
                while previous_workers > n_workers:
                    call(["kill", "-TTOU", pid])
                    previous_workers -= 1
        rewrite_unitfile()


def rewrite_unitfile():
    if os.path.exists("/etc/systemd/system/flask.service"):
        path, app, template = get_app_info()
        path = path.rstrip("/")
        pp = path.rsplit("/", 1)[0]

        unitfile_context = load_unitfile()
        unitfile_context["port"] = cfg["flask-port"]
        unitfile_context["pythonpath"] = pp
        unitfile_context["app"] = app
        unitfile_context["workers"] = cfg["workers"]

        render(
            source=template,
            target="/etc/systemd/system/flask.service",
            context=unitfile_context,
        )
        call(["systemctl", "daemon-reload"])


def get_app_info():
    if os.path.exists("/home/ubuntu/flask/flask-config"):
        file = open("/home/ubuntu/flask/flask-config", "r")
        line = file.readline()
        if line != "":
            path, app, template = line.split()
            return path, app, template
    return "", "", ""


def load_unitfile():
    if not os.path.isfile("unitfile.toml"):
        return {}

    with open("unitfile.toml") as fp:
        conf = toml.loads(fp.read())

    return conf


def gracefull_reload():
    if os.path.exists("/home/ubuntu/flask/master.pid"):
        with open("/home/ubuntu/flask/master.pid", "r") as f:
            pid = f.readline().strip()
            call(["kill", "-HUP", pid])
