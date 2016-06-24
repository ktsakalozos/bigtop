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
import os
from charms.reactive import RelationBase, when, when_not, is_state, set_state
from charms.layer.apache_bigtop_base import get_fqdn, get_layer_opts, Bigtop
from charmhelpers.core import hookenv, host
from charms import leadership
from charms.reactive.helpers import data_changed
from jujubigdata import utils


def install(master_host):
    roles = ['alluxio-worker']
    if is_state('leadership.is_leader'):
        roles.append('alluxio-master')
    override = {
        'alluxio::common::master_host': master_host,
    }

    bigtop = Bigtop()
    bigtop.render_site_yaml(roles=roles, overrides=override)
    bigtop.trigger_puppet()
    status = "ready"
    if is_state('leadership.is_leader'):
        status += " - master"

    with utils.environment_edit_in_place('/etc/environment') as env:
        env['ALLUXIO_HOME'] = '/usr/lib/alluxio'
        env['ALLUXIO_MASTER_ADDRESS'] = master_host

    # Temporary fix to start alluxio services BIGTOP-2487
    if not os.path.exists("/var/log/alluxio"):
        os.makedirs("/var/log/alluxio")

    host.service_start('alluxio-master')
    host.service_start('alluxio-worker')

    set_state('alluxio.started')
    return status


@when('bigtop.available')
@when_not('alluxio.started')
def install_alluxio():
    hookenv.status_set('maintenance', 'installing apache alluxio')
    master_host = leadership.leader_get('master-fqdn')
    if not master_host:
        return
    data_changed('master_host', master_host)
    status = install(master_host)
    for port in get_layer_opts().exposed_ports('alluxio'):
        hookenv.open_port(port)
    hookenv.status_set('active', status)


@when('leadership.changed.master-fqdn', 'alluxio.started')
def reinstall_alluxio():
    master_host = leadership.leader_get('master-fqdn')

    if not data_changed('master_host', master_host):
        return

    hookenv.status_set('maintenance', 'configuring alluxio master')
    status = install(master_host)
    hookenv.status_set('active', status)


@when('leadership.is_leader', 'bigtop.available')
def set_master_fqdn():
    master_host = get_fqdn()
    leadership.leader_set({'master-fqdn': master_host})
    hookenv.log("Setting Alluxio leader to {}".format(master_host))
