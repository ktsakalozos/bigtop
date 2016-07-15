from charmhelpers.core import hookenv
from charms.layer.bigtop_flume import Flume
from charms.reactive import set_state, remove_state, when, when_not
from jujubigdata.utils import DistConfig
from charms.reactive.helpers import data_changed


@when('bigtop.available', 'config.changed')
def starting_flume():
    hookenv.status_set('maintenance', 'configuring flume')
    flume_config = hookenv.config()['flume_config']
    flume = Flume()
    flume.configure(config)
    set_state('flume.started')
    hookenv.status_set('active', 'ready')


@when('bigtop.available')
@when_not('flume.started')
def waiting_for_config():
    hookenv.status_set('blocked', 'waiting for flume config')
