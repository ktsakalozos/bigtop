# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from jujubigdata import utils
from charms.layer.apache_bigtop_base import Bigtop
from charmhelpers.core import hookenv, host


class Sqoop(object):
    def __init__(self, dist_config):
        self.dist_config = dist_config

    def install_sqoop(self):

        bigtop = Bigtop()
        roles = ['sqoop']

        bigtop.render_site_yaml(roles=roles)
        bigtop.trigger_puppet()

        with utils.environment_edit_in_place('/etc/environment') as env:
            env['SQOOP_HOME'] = self.dist_config.path('sqoop')

    def open_ports(self):
        for port in self.dist_config.exposed_ports('sqoop'):
            hookenv.open_port(port)

    def close_ports(self):
        for port in self.dist_config.exposed_ports('sqoop'):
            hookenv.close_port(port)

    def restart(self):
        self.stop()
        self.start()

    def start(self):
        host.service_start('sqoop2-server')

    def stop(self):
        host.service_stop('sqoop2-server')
