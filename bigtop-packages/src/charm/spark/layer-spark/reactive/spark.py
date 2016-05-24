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
from charms.reactive import RelationBase, when, when_not, is_state, set_state, remove_state, when_any
from charms.layer.apache_bigtop_base import get_fqdn
from charms.layer.bigtop_spark import Spark
from charmhelpers.core import hookenv
from charms import leadership
from charms.reactive.helpers import data_changed
from charms.layer.hadoop_client import get_dist_config


def set_deployment_mode_state(state):
    if is_state('spark.yarn.installed'):
        remove_state('spark.yarn.installed')
    if is_state('spark.standalone.installed'):
        remove_state('spark.standalone.installed')
    remove_state('spark.ready.to.install')
    set_state('spark.started')
    set_state(state)


def report_status():
    mode = hookenv.config()['spark_execution_mode']
    if (not is_state('spark.yarn.installed')) and mode.startswith('yarn'):
        hookenv.status_set('blocked',
                           'yarn execution mode not available')
        return

    if mode == 'standalone' and is_state('leadership.is_leader'):
        mode = mode + " - master"

    hookenv.status_set('active', 'ready ({})'.format(mode))


def install_spark(hadoop=None):
    spark_master_host = leadership.leader_get('master-fqdn')
    hosts = {
        'spark-master': spark_master_host,
    }

    if is_state('hadoop.yarn.ready'):
        rms = hadoop.resourcemanagers()
        hosts['resourcemanager'] = rms[0]

    if is_state('hadoop.hdfs.ready'):
        nns = hadoop.namenodes()
        hosts['namenode'] = nns[0]

    dist = get_dist_config()
    spark = Spark(dist)
    spark.configure(hosts)


@when('bigtop.available')
@when_not('spark.started')
def first_install_spark():
    hookenv.status_set('maintenance', 'installing apache bitgop spark')
    install_spark()
    set_deployment_mode_state('spark.standalone.installed')
    report_status()


@when('config.changed', 'spark.started')
def reconfigure_spark():
    config = hookenv.config()
    mode = config['spark_execution_mode']
    hookenv.status_set('maintenance',
                       'changing default execution mode to {}'.format(mode))

    hadoop = (RelationBase.from_state('hadoop.yarn.ready') or
              RelationBase.from_state('hadoop.hdfs.ready'))

    install_spark(hadoop)
    report_status()


# This is a triky call. We want to fire when the leader changes, yarn and hdfs become ready or
# depart. In the future this should fire when Cassandra or any other storage
# becomes ready or departs. Since hdfs and yarn do not have a departed state we make sure
# we fire this method always ('spark.started'). We then build a deployment-matrix
# and if anything has changed we re-install.
# 'hadoop.yarn.ready', 'hadoop.hdfs.ready' can be ommited but I like them here for clarity
@when_any('leadership.changed.master-fqdn', 'hadoop.yarn.ready', 'hadoop.hdfs.ready', 'spark.started')
@when('bigtop.available')
def reinstall_spark():
    spark_master_host = leadership.leader_get('master-fqdn')
    deployment_matrix = {
        'spark_master': spark_master_host,
        'yarn_ready': is_state('hadoop.yarn.ready'),
        'hdfs_ready': is_state('hadoop.hdfs.ready'),
    }

    if not data_changed('deployment_matrix', deployment_matrix):
        return

    hookenv.status_set('maintenance', 'configuring spark')
    hadoop = (RelationBase.from_state('hadoop.yarn.ready') or
              RelationBase.from_state('hadoop.hdfs.ready'))
    install_spark(hadoop)
    if is_state('hadoop.yarn.ready'):
        set_deployment_mode_state('spark.yarn.installed')
    else:
        set_deployment_mode_state('spark.standalone.installed')

    report_status()


@when('leadership.is_leader', 'bigtop.available')
def send_fqdn():
    spark_master_host = get_fqdn()
    leadership.leader_set({'master-fqdn': spark_master_host})
    hookenv.log("Setting leader to {}".format(spark_master_host))


@when('spark.started', 'client.joined')
def client_present(client):
    client.set_spark_started()


@when('client.joined')
@when_not('spark.started')
def client_should_stop(client):
    client.clear_spark_started()
