
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
import json
from charms.reactive import is_state, remove_state, set_state, is_state, when, when_not
from charms.layer.apache_bigtop_base import Bigtop, get_layer_opts, get_fqdn
from charmhelpers.core import hookenv, host, unitdata
from jujubigdata import utils
from path import Path
from charms import leadership


###############################################################################
# Utility methods
###############################################################################
def send_early_install_info(remote):
    """Send clients/slaves enough relation data to start their install.

    If slaves or clients join before the namenode is installed, we can still provide enough
    info to start their installation. This will help parallelize installation among our
    cluster.

    Note that slaves can safely install early, but should not start until the
    'namenode.ready' state is set by the dfs-slave interface.
    """
    fqdn = get_fqdn()
    hdfs_port = get_layer_opts().port('namenode')
    webhdfs_port = get_layer_opts().port('nn_webapp_http')

    remote.send_namenodes([fqdn])
    remote.send_ports(hdfs_port, webhdfs_port)


def get_cluster_nodes():
    return json.loads(leadership.leader_get('cluster-nodes') or '[]')


def set_cluster_nodes(nodes):
    leadership.leader_set({
        'cluster-nodes': json.dumps(nodes),
    })


###############################################################################
# Core methods
###############################################################################
@when('bigtop.available')
@when_not('journal.started')
def init_ha_journalnode():
    ha_mode = hookenv.config()['ha']
    if not ha_mode:
        return

    hookenv.status_set('maintenance', 'installing journal node')
    bigtop = Bigtop()

    roles=[
        'journalnode',
    ]

    bigtop.render_site_yaml(
        hosts={
            'namenode': get_fqdn(),
        },
        roles=roles,
    )
    bigtop.trigger_puppet()

    hookenv.status_set('maintenance', 'journal node installed')
    set_state('journal.started')


@when('bigtop.available')
@when('journal.started')
@when('ssh_pub.ready', 'ssh_pri.ready')
@when_not('apache-bigtop-namenode.installed')
def install_namenode():
    ha_mode = hookenv.config()['ha']
    if ha_mode:
        selected_nodes = get_cluster_nodes()
        if len(selected_nodes) < 3:
            remain = 3 - len(selected_nodes)
            hookenv.status_set('blocked', 'waiting for {} more namenode units'.format(remain))
            return
        else:
            primary = selected_nodes[0]
            secondary = selected_nodes[1]
            third = selected_nodes[2]
    else:
        primary = get_fqdn()

    hookenv.status_set('maintenance', 'installing namenode')
    bigtop = Bigtop()

    roles=[
        'namenode',
	'mapred-app',
    ]

    extra = {}

    if ha_mode:
        if is_state('leadership.is_leader'):
            utils.run_as('root', 'hdfs', 'namenode', '-format')
        roles.append("standby-namenode")
        extra["bigtop::standby_head_node"] = secondary
        extra["hadoop::common_hdfs::ha"] = "manual"
        extra["hadoop::common_hdfs::hadoop_ha_sshfence_user_home"] = "/var/lib/hadoop-hdfs"
        extra["hadoop::common_hdfs::sshfence_privkey"] = "/home/hdfs/.ssh/id_rsa"
        extra["hadoop::common_hdfs::sshfence_pubkey"] = "/home/hdfs/.ssh/id_rsa.pub"
        extra["hadoop::common_hdfs::sshfence_user"] = "hdfs"
        extra["hadoop::common_hdfs::hadoop_ha_nameservice_id"] = "ha-nn-uri"
        extra["hadoop_cluster_node::hadoop_namenode_uri"] = "hdfs://%{hiera('hadoop_ha_nameservice_id')}:8020"
        extra["hadoop::common_hdfs::hadoop_namenode_host"] = [primary, secondary, third]
        share_edits = "qjournal://{}:8485;{}:8485;{}:8485/ha-nn-uri".format(primary, secondary, third)
        extra["hadoop::common_hdfs::shared_edits_dir"] = share_edits

    bigtop.render_site_yaml(
        hosts={
            'namenode': primary,
        },
        roles=roles,
        overrides=extra,
    )
    bigtop.trigger_puppet()

    # /etc/hosts entries from the KV are not currently used for bigtop,
    # but a hosts_map attribute is required by some interfaces (eg: dfs-slave)
    # to signify NN's readiness. Set our NN info in the KV to fulfill this
    # requirement.
    utils.initialize_kv_host()

    # make our namenode listen on all interfaces
    hdfs_site = Path('/etc/hadoop/conf/hdfs-site.xml')
    with utils.xmlpropmap_edit_in_place(hdfs_site) as props:
        props['dfs.namenode.rpc-bind-host'] = '0.0.0.0'
        props['dfs.namenode.servicerpc-bind-host'] = '0.0.0.0'
        props['dfs.namenode.http-bind-host'] = '0.0.0.0'
        props['dfs.namenode.https-bind-host'] = '0.0.0.0'

    set_state('apache-bigtop-namenode.installed')
    hookenv.status_set('maintenance', 'namenode installed')


@when('apache-bigtop-namenode.installed')
@when_not('apache-bigtop-namenode.started')
def start_namenode():
    hookenv.status_set('maintenance', 'starting namenode')
    # NB: service should be started by install, but this may be handy in case
    # we have something that removes the .started state in the future. Also
    # note we restart here in case we modify conf between install and now.
    host.service_restart('hadoop-hdfs-namenode')
    for port in get_layer_opts().exposed_ports('namenode'):
        hookenv.open_port(port)
    set_state('apache-bigtop-namenode.started')
    hookenv.status_set('maintenance', 'namenode started')


@when('namenode-cluster.joined')
@when('leadership.is_leader')
def check_cluster_nodes(cluster):
    nodes = cluster.nodes()
    # The first node that joins the leader in the cluster is going to be
    # the secondary namenode.
    # The primary namenode is going to be leader.
    # The above selection should change only when the secondary node departs
    # or the leader changes.
    if not unitdata.kv().get('ha.config.ready', False) and len(nodes) >= 2:
        unitdata.kv().set('ha.config.ready', True)
        units_map = cluster.hosts_map()
        set_cluster_nodes(list(units_map.keys()))


@when('bigtop.available')
@when('leadership.is_leader')
@when_not('leadership.set.ssh-key-pub')
def generate_ssh_key():
    # We need to create the 'mapred' user/group since we are not installing
    # hadoop-mapreduce. This is needed so the namenode can access yarn
    # job history files in hdfs. Also add our ubuntu user to the hadoop
    # and mapred groups.
    get_layer_opts().add_users()

    utils.generate_ssh_key('hdfs')
    leadership.leader_set({
        'ssh-key-priv': utils.ssh_priv_key('hdfs').text(),
        'ssh-key-pub': utils.ssh_pub_key('hdfs').text(),
    })


@when('leadership.changed.ssh-key-pub')
def install_ssh_pub_key():
    ssh_dir = Path("/var/lib/hadoop-hdfs/.ssh/")
    ssh_dir.makedirs_p()
    authfile = ssh_dir / 'authorized_keys'
    authfile.write_lines([leadership.leader_get('ssh-key-pub')], append=True)
    keyfile = ssh_dir / 'id_rsa.pub'
    keyfile.write_text(leadership.leader_get('ssh-key-pub'))
    set_state('ssh_pub.ready')


@when('leadership.changed.ssh-key-priv')
def install_ssh_priv_key():
    ssh_dir = Path("/var/lib/hadoop-hdfs/.ssh/")
    ssh_dir.makedirs_p()
    keyfile = ssh_dir / 'id_rsa'
    keyfile.write_text(leadership.leader_get('ssh-key-priv'))
    os.chmod(keyfile, 600)
    set_state('ssh_pri.ready')


###############################################################################
# Slave methods
###############################################################################
@when('datanode.joined')
@when_not('apache-bigtop-namenode.installed')
def send_dn_install_info(datanode):
    """Send datanodes enough relation data to start their install."""
    send_early_install_info(datanode)


@when('apache-bigtop-namenode.started', 'datanode.joined')
def send_dn_all_info(datanode):
    """Send datanodes all dfs-slave relation data.

    At this point, the namenode is ready to serve datanodes. Send all
    dfs-slave relation data so that our 'namenode.ready' state becomes set.
    """
    bigtop = Bigtop()
    fqdn = get_fqdn()
    hdfs_port = get_layer_opts().port('namenode')
    webhdfs_port = get_layer_opts().port('nn_webapp_http')

    datanode.send_spec(bigtop.spec())
    datanode.send_namenodes([fqdn])
    datanode.send_ports(hdfs_port, webhdfs_port)

    # hosts_map, ssh_key, and clustername are required by the dfs-slave
    # interface to signify NN's readiness. Send them, even though they are not
    # utilized by bigtop.
    # NB: update KV hosts with all datanodes prior to sending the hosts_map
    # because dfs-slave gates readiness on a DN's presence in the hosts_map.
    utils.update_kv_hosts(datanode.hosts_map())
    datanode.send_hosts_map(utils.get_kv_hosts())
    datanode.send_ssh_key('invalid')
    datanode.send_clustername(hookenv.service_name())

    # update status with slave count and report ready for hdfs
    num_slaves = len(datanode.nodes())
    hookenv.status_set('active', 'ready ({count} datanode{s})'.format(
        count=num_slaves,
        s='s' if num_slaves > 1 else '',
    ))
    set_state('apache-bigtop-namenode.ready')


@when('apache-bigtop-namenode.started', 'datanode.departing')
def remove_dn(datanode):
    """Handle a departing datanode.

    This simply logs a message about a departing datanode and removes
    the entry from our KV hosts_map. The hosts_map is not used by bigtop, but
    it is required for the 'namenode.ready' state, so we may as well keep it
    accurate.
    """
    slaves_leaving = datanode.nodes()  # only returns nodes in "departing" state
    hookenv.log('Datanodes leaving: {}'.format(slaves_leaving))
    utils.remove_kv_hosts(slaves_leaving)
    datanode.dismiss()


@when('apache-bigtop-namenode.started')
@when_not('datanode.joined')
def wait_for_dn():
    remove_state('apache-bigtop-namenode.ready')
    # NB: we're still active since a user may be interested in our web UI
    # without any DNs, but let them know hdfs is caput without a DN relation.
    hookenv.status_set('active', 'hdfs requires a datanode relation')


###############################################################################
# Client methods
###############################################################################
@when('namenode.clients')
@when_not('apache-bigtop-namenode.installed')
def send_client_install_info(client):
    """Send clients enough relation data to start their install."""
    send_early_install_info(client)


@when('apache-bigtop-namenode.started', 'namenode.clients')
def send_client_all_info(client):
    """Send clients (plugin, RM, non-DNs) all dfs relation data.

    At this point, the namenode is ready to serve clients. Send all
    dfs relation data so that our 'namenode.ready' state becomes set.
    """
    bigtop = Bigtop()
    fqdn = get_fqdn()
    hdfs_port = get_layer_opts().port('namenode')
    webhdfs_port = get_layer_opts().port('nn_webapp_http')

    client.send_spec(bigtop.spec())
    client.send_namenodes([fqdn])
    client.send_ports(hdfs_port, webhdfs_port)
    # namenode.ready implies we have at least 1 datanode, which means hdfs
    # is ready for use. Inform clients of that with send_ready().
    if is_state('apache-bigtop-namenode.ready'):
        client.send_ready(True)
    else:
        client.send_ready(False)

    # hosts_map and clustername are required by the dfs interface to signify
    # NN's readiness. Send it, even though they are not utilized by bigtop.
    client.send_hosts_map(utils.get_kv_hosts())
    client.send_clustername(hookenv.service_name())
