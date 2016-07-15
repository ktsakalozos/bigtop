import os
from charmhelpers.core import hookenv
from charmhelpers.core import host
from jujubigdata import utils
from charms.layer.apache_bigtop_base import Bigtop
from charms import layer


class Flume(object):
    def __init__(self, dist_config=None):
        self.dist_config = dist_config or utils.DistConfig(data=layer.options('apache-bigtop-base'))

    def configure(self, config):
        roles = ['flume-agent']
        bigtop = Bigtop()
        bigtop.render_site_yaml(roles=roles)
        bigtop.trigger_puppet()

        conf_file = open('/etc/flume/conf/flume.conf', 'w')
        conf_file.write(config)
        conf_file.close()
        self.restart()

    def restart(self):
        self.stop()
        self.start()

    def start(self):
        host.service_start('flume-agent')

    def stop(self):
        host.service_stop('flume-agent')
