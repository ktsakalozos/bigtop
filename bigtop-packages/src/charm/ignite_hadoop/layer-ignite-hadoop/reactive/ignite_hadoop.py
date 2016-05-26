from charms.reactive import when, when_not, is_state, set_state
from charms.reactive.helpers import data_changed
from charms.layer.apache_bigtop_base import Bigtop
from charmhelpers.core import hookenv


@when('bigtop.available')
@when('namenode.joined')
def install_ignite(namenode):
    namenodes = namenode.namenodes()
    if not namenodes:
        hookenv.status_set('waiting', 'waiting on namenode')
        return
    if data_changed('ignite.namenodes', namenodes):
        installed = is_state('ignite.installed')
        action = 'installing' if not installed else 'configuring'
        hookenv.status_set('maintenance', '%s ignite' % action)
        bigtop = Bigtop()
        bigtop.render_site_yaml(
            hosts={
                'namenode': namenodes[0],
            },
            roles=[
                'ignite-server',
            ],
        )
        bigtop.trigger_puppet()
        hookenv.status_set('active', 'ready')
        set_state('ignite.installed')


@when('bigtop.available')
@when_not('namenode.joined')
def blocked():
    hookenv.status_set('blocked', 'waiting on relation to namenode')
