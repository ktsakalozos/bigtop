# Big Data Ingestion with Apache Kafka packaged by Apache Bigtop

This bundle is an 11 node cluster designed to scale out. Built around Apache
Hadoop components, it contains the following units:

  * 1 NameNode (HDFS)
  * 1 ResourceManager (YARN)
  * 3 Slaves (DataNode and NodeManager)
  * 1 Flume-HDFS
    - 1 Plugin (colocated on the Flume unit)
  * 1 Flume-Kafka
  * 1 Kafka
  * 1 Zookeeper

The Flume-HDFS unit provides an Apache Flume agent featuring an Avro source,
memory channel, and HDFS sink. This agent supports a relation with the
Flume-Kafka charm (`apache-flume-kafka`) to ingest messages published to a
given Kafka topic into HDFS.


## Usage

Deploy this bundle using juju-quickstart:

    juju deploy kafka-ingestion

> Note: With Juju versions < 2.0, you will need to use [juju-deployer][] to
deploy the bundle.


## Configuration

The default Kafka topic where messages are published is unset. Set this to
an existing Kafka topic as follows:

    juju set-config flume-kafka kafka_topic='<topic_name>'

If you don't have a Kafka topic, you may create one (and verify successful
creation) with:

    juju run-action kafka/0 create-topic topic=<topic_name> \
     partitions=1 replication=1
    juju show-action-output <id>  # <-- id from above command

Once the Flume agents start, messages will start flowing into
HDFS in year-month-day directories here: `/user/flume/flume-kafka/%y-%m-%d`.


## Verify the deployment

The services provide extended status reporting to indicate when they are ready:

    juju status --format=tabular

This is particularly useful when combined with `watch` to track the on-going
progress of the deployment:

    watch -n 0.5 juju status --format=tabular

The charm for each core component (namenode, resourcemanager, kafka)
also each provide a `smoke-test` action that can be used to verify that each
component is functioning as expected.  You can run them all and then watch the
action status list:

    juju run-action namenode/0 smoke-test
    juju run-action resourcemanager/0 smoke-test
    juju run-action kafka/0 smoke-test
    watch -n 0.5 juju action status

Eventually, all of the actions should settle to `status: completed`.  If
any go instead to `status: failed` then it means that component is not working
as expected.  You can get more information about that component's smoke test:

    juju show-action-output <action-id>

### Smoke test Flume
Verify the flume java process is running on the flume-hdfs unit:

    juju run --unit flume-hdfs/0 'ps -ef | grep java'

### Test Kafka-Flume
A Kafka topic is required for this test. Topic creation is covered in the
**Configuration** section above. Generate Kafka messages with the `write-topic`
action:

    juju action do kafka/0 write-topic topic=<topic_name> data="This is a test"

To verify these messages are being stored into HDFS, SSH to the `flume-hdfs`
unit, locate an event, and cat it:

    juju ssh flume-hdfs/0
    hdfs dfs -ls /user/flume/flume-kafka  # <-- find a date
    hdfs dfs -ls /user/flume/flume-kafka/yyyy-mm-dd  # <-- find an event
    hdfs dfs -cat /user/flume/flume-kafka/yyyy-mm-dd/FlumeData.[id]


## Scaling

This bundle was designed to scale out. To increase the amount of
slaves, you can add units to the slave service. To add one unit:

    juju add-unit slave

Or you can add multiple units at once:

    juju add-unit -n4 slave


## Connecting External Clients

By default, this bundle does not expose Kafka outside of the provider's network.
To allow external clients to connect to Kafka, first expose the service:

    juju expose kafka

Next, ensure the external client can resolve the short hostname of the kafka
unit. A simple way to do this is to add an `/etc/hosts` entry on the external
kafka client machine. Gather the needed info from juju:

    user@juju-client$ juju run --unit kafka/0 'hostname -s'
    kafka-0
    user@juju-client$ juju status --format=yaml kafka/0 | grep public-address
    public-address: 40.784.149.135

Update `/etc/hosts` on the external kafka client:

    user@kafka-client$ echo "40.784.149.135 kafka-0" | sudo tee -a /etc/hosts

The external kafka client should now be able to access Kafka by using
`kafka-0:9092` as the broker.


## Contact Information

- <bigdata@lists.ubuntu.com>


## Help

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
