from jujubigdata import utils
from charms.layer.apache_bigtop_base import Bigtop
from path import Path
from charmhelpers.core import host, hookenv 
from charms import layer


class Oozie(object):
    def __init__(self, dist_config):
        self.dist_config = dist_config #or utils.DistConfig(data=layer.options('apache-bigtop-base'))

    def install_oozie(self):
        roles = ['hadoop-client']

        bigtop = Bigtop()
        bigtop.render_site_yaml(roles=roles)
        bigtop.trigger_puppet()

        roles = ['oozie-server']

        bigtop.render_site_yaml(roles=roles)
        bigtop.trigger_puppet()

    def open_ports(self):
        for port in self.dist_config.exposed_ports('oozie'):
            hookenv.open_port(port)

    def restart(self):
        self.stop()
        self.start()

    def start(self):
        host.service_start('oozie-server')

    def stop(self):
        host.service_stop('oozie-server')
