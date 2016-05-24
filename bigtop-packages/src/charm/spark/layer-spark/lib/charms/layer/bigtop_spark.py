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
from path import Path
from charms.reactive import is_state
from charmhelpers.core import hookenv
from charmhelpers.core import host
from charmhelpers.core import unitdata
from jujubigdata import utils
from charms.layer.apache_bigtop_base import Bigtop
from charmhelpers.fetch.archiveurl import ArchiveUrlFetchHandler


class Spark(object):

    def __init__(self, dist_config):
        self.dist_config = dist_config

    # translate our execution_mode into the appropriate --master value
    def get_master_url(self, spark_master_host):
        mode = hookenv.config()['spark_execution_mode']
        master = None
        if mode.startswith('local') or mode == 'yarn-cluster':
            master = mode
        elif mode == 'standalone':
            master = 'spark://{}:7077'.format(spark_master_host)
        elif mode.startswith('yarn'):
            master = 'yarn-client'
        return master

    def get_roles(self):
        roles = ['spark-worker', 'spark-client']
        if is_state('leadership.is_leader'):
            roles.append('spark-master')
            roles.append('spark-history-server')
        return roles

    def install_benchmark(self):
        install_sb = hookenv.config()['spark_bench_enabled']
        sb_dir = '/home/ubuntu/spark-bench'
        if install_sb:
            if not unitdata.kv().get('spark_bench.installed', False):
                if utils.cpu_arch() == 'ppc64le':
                    sb_url = hookenv.config()['spark_bench_ppc64le']
                else:
                    # TODO: may need more arch cases (go with x86 sb for now)
                    sb_url = hookenv.config()['spark_bench_x86_64']

                Path(sb_dir).rmtree_p()
                au = ArchiveUrlFetchHandler()
                au.install(sb_url, '/home/ubuntu')

                # #####
                # Handle glob if we use a .tgz that doesn't expand to sb_dir
                # sb_archive_dir = glob('/home/ubuntu/spark-bench-*')[0]
                # SparkBench expects to live in ~/spark-bench, so put it there
                # Path(sb_archive_dir).rename(sb_dir)
                # #####

                unitdata.kv().set('spark_bench.installed', True)
                unitdata.kv().flush(True)
        else:
            Path(sb_dir).rmtree_p()
            unitdata.kv().set('spark_bench.installed', False)
            unitdata.kv().flush(True)

    def setup(self):
        self.dist_config.add_users()
        self.dist_config.add_dirs()
        self.install_demo()
        self.open_ports()

    def setup_hdfs_logs(self):
        # create hdfs storage space for history server
        dc = self.dist_config
        events_dir = dc.path('spark_events')
        events_dir = 'hdfs://{}'.format(events_dir)
        utils.run_as('hdfs', 'hdfs', 'dfs', '-mkdir', '-p', events_dir)
        utils.run_as('hdfs', 'hdfs', 'dfs', '-chown', '-R', 'ubuntu:spark',
                     events_dir)
        return events_dir

    def configure(self, available_hosts):
        """
        This is the core logic of setting up spark.

        Two flags are needed:

          * Namenode exists aka HDFS is there
          * Resource manager exists aka YARN is ready

        both flags are infered from the available hosts.

        :param dict available_hosts: Hosts that Spark should know about.
        """

        if not unitdata.kv().get('spark.bootstrapped', False):
            self.setup()
            unitdata.kv().set('spark.bootstrapped', True)

        self.install_benchmark()

        hosts = {
            'spark': available_hosts['spark-master'],
        }

        dc = self.dist_config
        events_log_dir = 'file://{}'.format(dc.path('spark_events'))
        if 'namenode' in available_hosts:
            hosts['namenode'] = available_hosts['namenode']
            events_log_dir = self.setup_hdfs_logs()

        if 'resourcemanager' in available_hosts:
            hosts['resourcemanager'] = available_hosts['resourcemanager']

        roles = self.get_roles()

        override = {
            'spark::common::master_url': self.get_master_url(available_hosts['spark-master']),
            'spark::common::event_log_dir': events_log_dir,
            'spark::common::history_log_dir': events_log_dir,
        }

        bigtop = Bigtop()
        bigtop.render_site_yaml(hosts, roles, override)
        bigtop.trigger_puppet()
        # There is a race condition here.
        # The work role will not start the first time we trigger puppet apply.
        # The exception in /var/logs/spark:
        # Exception in thread "main" org.apache.spark.SparkException: Invalid master URL: spark://:7077
        # The master url is not set at the time the worker start the first time.
        # TODO(kjackal): ...do the needed... (investiate,debug,submit patch)
        bigtop.trigger_puppet()
        if 'namenode' not in available_hosts:
            # Make sure users other than spark can access the events logs dir and run jobs
            utils.run_as('root', 'chmod', '777', dc.path('spark_events'))

    def install_demo(self):
        '''
        Install sparkpi.sh to /home/ubuntu (executes SparkPI example app)
        '''
        demo_source = 'scripts/sparkpi.sh'
        demo_target = '/home/ubuntu/sparkpi.sh'
        Path(demo_source).copy(demo_target)
        Path(demo_target).chmod(0o755)
        Path(demo_target).chown('ubuntu', 'hadoop')

    def start(self):
        if unitdata.kv().get('spark.uprading', False):
            return

        # stop services (if they're running) to pick up any config change
        self.stop()
        # always start the history server, start master/worker if we're standalone
        host.service_start('spark-history-server')
        if hookenv.config()['spark_execution_mode'] == 'standalone':
            host.service_start('spark-master')
            host.service_start('spark-worker')

    def stop(self):
        if not unitdata.kv().get('spark.installed', False):
            return
        # Only stop services if they're running
        if utils.jps("HistoryServer"):
            host.service_stop('spark-history-server')
        if utils.jps("Master"):
            host.service_stop('spark-master')
        if utils.jps("Worker"):
            host.service_stop('spark-worker')

    def open_ports(self):
        for port in self.dist_config.exposed_ports('spark'):
            hookenv.open_port(port)

    def close_ports(self):
        for port in self.dist_config.exposed_ports('spark'):
            hookenv.close_port(port)
