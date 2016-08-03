
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
from charms.reactive import is_state, remove_state, set_state, is_state, when, when_not, when_any
from charms.layer.apache_bigtop_base import Bigtop, get_layer_opts, get_fqdn
from charmhelpers.core import hookenv, host, unitdata
from jujubigdata import utils
from path import Path
from charms import leadership
from charms.reactive.helpers import data_changed


###############################################################################
# Utility methods
###############################################################################
def get_namenodes():
    if is_state("nonha.setup"):
        fqdn = get_fqdn()
        return [fqdn]
    elif is_state("ha.setup") and is_state('ha.cluster.ready'):
        cluster_nodes = get_nodes('cluster')
        return [cluster_nodes[0], cluster_nodes[1]]
    else:
        return None


def send_early_install_info(remote):
    """Send clients/slaves enough relation data to start their install.

    If slaves or clients join before the namenode is installed, we can still provide enough
    info to start their installation. This will help parallelize installation among our
    cluster.

    Note that slaves can safely install early, but should not start until the
    'namenode.ready' state is set by the dfs-slave interface.
    """
    hdfs_port = get_layer_opts().port('namenode')
    webhdfs_port = get_layer_opts().port('nn_webapp_http')

    namenodes = get_namenodes()
    if namenodes:
        remote.send_namenodes(namenodes)

    remote.send_ports(hdfs_port, webhdfs_port)


def additional_hosts_and_hdfs_config():
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


###############################################################################
# Core methods
###############################################################################
@when('bigtop.available', 'nonha.setup')
@when_not('apache-bigtop-namenode.installed')
def install_namenode():
    hookenv.status_set('maintenance', 'installing namenode')
    bigtop = Bigtop()

    roles=[
        'namenode',
	'mapred-app',
    ]

    bigtop.render_site_yaml(
        hosts={
            'namenode': get_fqdn(),
        },
        roles=roles,
    )
    bigtop.trigger_puppet()

    additional_hosts_and_hdfs_config()

    # We need to create the 'mapred' user/group since we are not installing
    # hadoop-mapreduce. This is needed so the namenode can access yarn
    # job history files in hdfs. Also add our ubuntu user to the hadoop
    # and mapred groups.
    get_layer_opts().add_users()

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

    if is_state('leadership.is_leader'):
        leadership.leader_set({ 'hdfs_formated': True })
    hookenv.status_set('maintenance', 'namenode started')



@when('leadership.changed.hdfs_formated')
def hdfs_formated():
    set_state('hdfs.formated')


###############################################################################
# HA
###############################################################################
# HA -- mark HA setup
###############################################################################
@when('bigtop.available')
@when_not('setup.marked')
def mark_ha_setup():
    setup_mode = hookenv.config()['ha']
    if setup_mode:
        set_state('ha.setup')
        autofail = hookenv.config()['autofailover']
        if autofail:
            set_state("auto.ha")
        else:
            set_state("manual.ha")
    else:
        set_state('nonha.setup')

    set_state('setup.marked')


@when('bigtop.available', 'ha.setup')
@when_not('ha.cluster.ready')
def wait_for_ha_setup():
    hookenv.status_set('blocked', 'waiting for 3 namenode units')


###############################################################################
# HA -- ssh keys setup
###############################################################################
@when('bigtop.available', 'leadership.is_leader', 'ha.setup')
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
# HA -- management of namenodes and journalnodes clusters
###############################################################################
@when('namenode-cluster.joined', 'leadership.is_leader', 'ha.setup')
def gather_cluster_nodes(cluster):
    cluster_nodes = cluster.cluster_nodes()
    journal_nodes = cluster.ready_nodes_with_journal()
    # The first node that joins with the leader in the cluster is going to be
    # the secondary namenode.
    # The primary namenode is going to be leader.
    if not is_state('ha.cluster.ready') and len(cluster_nodes) >= 2:
        cluster_nodes.insert(0, get_fqdn())
        set_nodes('cluster', cluster_nodes)

    if not is_state('ha.journal.ready') and len(journal_nodes) >= 2:
        journal_nodes.insert(0, get_fqdn())
        set_nodes('journal', journal_nodes)


def get_nodes(type):
    return json.loads(leadership.leader_get(type) or '[]')


def set_nodes(type, nodes):
    leadership.leader_set({
        type: json.dumps(nodes),
    })


@when('leadership.changed.cluster')
def cluster_nodes_udated():
    set_state('ha.cluster.ready')


@when('leadership.changed.journal')
def journal_nodes_updated():
    set_state('ha.journal.ready')


@when('bigtop.available')
@when('namenode-cluster.joined')
def send_cluster_nodes_fqdn(cluster):
    fqdn = get_fqdn()
    cluster.clusternode_ready(fqdn)


@when('bigtop.available')
@when('namenode-cluster.joined', 'journal.started')
def send_journal_nodes_fqdn(cluster):
    fqdn = get_fqdn()
    cluster.journalnode_ready(fqdn)


###############################################################################
# HA -- handle zookeeper nodes
###############################################################################
@when('zookeeper.joined', 'leadership.is_leader', 'ha.setup', 'auto.ha')
def gather_zookeeper_nodes(zkcluster):
    zks = zkcluster.zookeepers()
    if not data_changed('zknodes', zks) or not zks:
        return

    set_nodes('zookeeper', zks)


@when('leadership.changed.zookeeper')
def zookeeper_nodes_udated():
    set_state('zookeepers.ready')

    # If hadoop-hdfs-zkfc we need to update core-site.xml with the quorum
    # and restart the service.
    if host.service_running('hadoop-hdfs-zkfc'):
        host.service_stop('hadoop-hdfs-zkfc')
        core_site = Path('/etc/hadoop/conf/core-site.xml')
        with utils.xmlpropmap_edit_in_place(core_site) as props:
            props['ha.zookeeper.quorum'] = get_zookeeper_quorum_string()
        host.service_start('hadoop-hdfs-zkfc')


def get_zookeeper_quorum_string():
    zk_units = get_nodes('zookeeper')
    zks = []
    for unit in zk_units:
        ip = utils.resolve_private_address(unit['host'])
        zks.append("%s:%s" % (ip, unit['port']))
        zks.sort()
    zk_connect = ",".join(zks)
    return zk_connect


###############################################################################
# HA -- Start services
###############################################################################
def get_bigtop_overrides(nodes):
    if not is_state('ha.setup'):
        return {}
    else:
        primary = nodes[0]
        secondary = nodes[1]
        third = nodes[2]

        extra = {}
        extra["bigtop::standby_head_node"] = secondary
        extra["hadoop::common_hdfs::ha"] = "manual"
        extra["hadoop::common_hdfs::hadoop_ha_sshfence_user_home"] = "/var/lib/hadoop-hdfs"
        extra["hadoop::common_hdfs::sshfence_privkey"] = "/home/hdfs/.ssh/id_rsa"
        extra["hadoop::common_hdfs::sshfence_pubkey"] = "/home/hdfs/.ssh/id_rsa.pub"
        extra["hadoop::common_hdfs::sshfence_user"] = "hdfs"
        extra["hadoop::common_hdfs::hadoop_ha_nameservice_id"] = "ha-nn-uri"
        extra["hadoop_cluster_node::hadoop_namenode_uri"] = "hdfs://%{hiera('hadoop_ha_nameservice_id')}:8020"
        extra["hadoop::common_hdfs::hadoop_namenode_host"] = [primary, secondary]
        share_edits = "qjournal://{}:8485;{}:8485;{}:8485/ha-nn-uri".format(primary, secondary, third)
        extra["hadoop::common_hdfs::shared_edits_dir"] = share_edits
        return extra


@when('bigtop.available', 'ha.cluster.ready', 'ssh_pub.ready', 'ssh_pri.ready', 'ha.setup')
@when_not('journal.started')
def start_ha_journalnode():
    cluster_nodes = get_nodes('cluster')
    extra = get_bigtop_overrides(cluster_nodes)

    hookenv.status_set('maintenance', 'installing journal node')
    bigtop = Bigtop()

    roles=[
        'journalnode',
    ]

    bigtop.render_site_yaml(
        hosts={
            'namenode': cluster_nodes[0],
        },
        roles=roles,
        overrides=extra,
    )
    bigtop.trigger_puppet()

    hookenv.status_set('maintenance', 'journal node installed')
    set_state('journal.started')


@when('bigtop.available', 'ha.setup', 'ssh_pub.ready', 'ssh_pri.ready')
@when_any('ha.journal.ready', 'hdfs.formated', 'zookeepers.ready')
@when_not('apache-bigtop-namenode.installed')
def install_ha_namenode():
    if is_state('auto.ha') and not is_state('zookeepers.ready'):
        hookenv.status_set('blocked', 'waiting for relation to zookeeper')
        return

    if not is_state('leadership.is_leader') and not is_state('hdfs.formated'):
        hookenv.status_set('waiting', 'waiting for leader to format hdfs')
        return

    if not is_state('ha.journal.ready'):
        hookenv.status_set('waiting', 'waiting for journal nodes to become ready')
        return

    hookenv.status_set('maintenance', 'installing ha namenode')
    journal_nodes = get_nodes('journal')
    extra = get_bigtop_overrides(journal_nodes)
    if is_state('auto.ha'):
        extra["hadoop::common_hdfs::ha"] = "auto"
        extra["hadoop::zk"] = get_zookeeper_quorum_string()

    extra["bigtop::roles"] = [ 'namenode', 'mapred-app', 'standby-namenode' ]
    bigtop = Bigtop()

    roles=[
        'namenode',
	'mapred-app',
        'standby-namenode',
    ]

    host.chownr("/data", "hdfs", "hdfs", chowntopdir=True)
    if is_state('leadership.is_leader'):
        utils.run_as('hdfs', 'hdfs', 'namenode', '-format', ' -nonInteractive')

    bigtop.render_site_yaml(
        hosts={
            'namenode': journal_nodes[0],
        },
        roles=roles,
        overrides=extra,
    )
    bigtop.trigger_puppet()

    additional_hosts_and_hdfs_config()

    if get_fqdn() != journal_nodes[2] and not is_state('auto.ha'):
        utils.run_as('hdfs', 'hdfs', 'namenode', '-bootstrapStandby')
        host.service_start('hadoop-hdfs-namenode')
        utils.run_as('hdfs', 'hdfs', 'haadmin', '-transitionToActive', 'nn1')
    elif get_fqdn() == journal_nodes[2]:
        set_state("journalnode.only")
        host.service_stop('hadoop-hdfs-namenode')
        if is_state('auto.ha') and host.service_running('hadoop-hdfs-zkfc'):
            host.service_stop('hadoop-hdfs-zkfc')
        set_state('apache-bigtop-namenode.started')

    set_state('apache-bigtop-namenode.installed')
    hookenv.status_set('maintenance', 'namenode installed')


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
    datanode.send_namenodes(get_namenodes())
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
    if is_state('journalnode.only'):
        hookenv.status_set('active', 'ready - journal node only')
    else:
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
    hdfs_port = get_layer_opts().port('namenode')
    webhdfs_port = get_layer_opts().port('nn_webapp_http')

    client.send_spec(bigtop.spec())
    client.send_namenodes(get_namenodes())
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
