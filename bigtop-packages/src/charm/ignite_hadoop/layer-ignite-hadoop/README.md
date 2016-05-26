<!--
  Licensed to the Apache Software Foundation (ASF) under one or more
  contributor license agreements.  See the NOTICE file distributed with
  this work for additional information regarding copyright ownership.
  The ASF licenses this file to You under the Apache License, Version 2.0
  (the "License"); you may not use this file except in compliance with
  the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->
## Overview

Apache Ignite In-Memory Data Fabric is a high-performance, integrated and
distributed in-memory platform for computing and transacting on large-scale
data sets in real-time, orders of magnitude faster than possible with
traditional disk-based or flash technologies.

This charm adds Ignite to an Apache Hadoop cluster to enhance the performance
by providing HDFS caching and in-memory MapReduce.


## Usage

This charm is intended to be added to an existing Hadoop cluster, deployed via
one of the [apache bigtop bundles](https://jujucharms.com/u/bigdata-charmers/#bundles).
For example:

    juju deploy hadoop-processing

> Note: With Juju versions < 2.0, you will need to use [juju-deployer][] to
deploy the bundle.

This will deploy the Apache Bigtop Hadoop platform with a workload node
preconfigured to work with the cluster.

You can then add Ignite by relating it to the resourcemanager and namenode:

    juju deploy cs:trusty/ignite-hadoop
    juju add-relation ignite-hadoop resourcemanager
    juju add-relation ignite-hadoop namenode


[juju-deployer]: https://pypi.python.org/pypi/juju-deployer/


## Status and Smoke Test

Apache Bigtop charms provide extended status reporting to indicate when they
are ready:

    juju status --format=tabular

This is particularly useful when combined with `watch` to track the on-going
progress of the deployment:

    watch -n 0.5 juju status --format=tabular

The message for each unit will provide information about that unit's state.
Once they all indicate that they are ready, you can perform a "smoke test"
to verify HDFS or YARN services are working as expected. Trigger the
`smoke-test` action by:

    juju action do ignite-hadoop/0 smoke-test

After a few seconds or so, you can check the results of the smoke test:

    juju action status

You will see `status: completed` if the smoke test was successful, or
`status: failed` if it was not.  You can get more information on why it failed
via:

    juju action fetch <action-id>


## Deploying in Network-Restricted Environments

Charms can be deployed in environments with limited network access. To deploy
in this environment, you will need a local mirror to serve required packages.


### Mirroring Packages

You can setup a local mirror for apt packages using squid-deb-proxy.
For instructions on configuring juju to use this, see the
[Juju Proxy Documentation](https://juju.ubuntu.com/docs/howto-proxies.html).


## Contact Information

- <bigdata@lists.ubuntu.com>


## Hadoop

- [Apache Bigtop](http://bigtop.apache.org/) home page
- [Apache Bigtop issue tracking](http://bigtop.apache.org/issue-tracking.html)
- [Apache Bigtop mailing lists](http://bigtop.apache.org/mail-lists.html)
- [Apache Bigtop charms](https://jujucharms.com/q/apache/bigtop)
