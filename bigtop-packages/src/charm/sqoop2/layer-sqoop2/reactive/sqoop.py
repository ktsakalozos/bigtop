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

from charmhelpers.core import hookenv
from charms.layer.bigtop_sqoop import Sqoop
from charms.reactive import is_state, set_state, remove_state, when, when_not
from charms.layer.hadoop_client import get_dist_config


@when('bigtop.available')
def report_status():
    hadoop_joined = is_state('hadoop.joined')
    hadoop_ready = is_state('hadoop.ready')
    if not hadoop_joined:
        hookenv.status_set('blocked',
                           'waiting for relation to hadoop plugin')
    elif not hadoop_ready:
        hookenv.status_set('waiting',
                           'waiting for hadoop')


@when('bigtop.available', 'hadoop.ready')
@when_not('sqoop.installed')
def install_sqoop(hadoop):
    hookenv.status_set('maintenance', 'installing sqoop2 server')
    dist = get_dist_config()
    sqoop = Sqoop(dist)
    sqoop.install_sqoop()
    sqoop.open_ports()
    sqoop.start()
    set_state('sqoop.installed')
    hookenv.status_set('active', 'ready')


@when('sqoop.installed')
@when_not('hadoop.ready')
def stop_server():
    dist = get_dist_config()
    sqoop = Sqoop(dist)
    sqoop.stop()
    sqoop.close_ports()
    remove_state('sqoop.installed')
