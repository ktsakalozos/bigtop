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

Apache Sqoop is a tool designed for efficiently transferring data betweeen
structured,semi-structured and unstructured data sources. Relational databases
are examples of structured data sources with well defined schema for the data
they store. Cassandra, Hbase are examples of semi-structured data sources and
HDFS is an example of unstructured data source that Sqoop can support.

## Usage

This charm is intended to be deployed in addition to one of the
[big data bundles](https://jujucharms.com/u/bigdata-charmers/#bundles).
For example:

    juju deploy hadoop-processing

_**Note**: The above assumes Juju 2.0 or greater. If using an earlier version
 +of Juju, the syntax is `juju-quickstart hadoop-processing`._

Once this step is complete, deploy and relate sqoop:

    juju deploy sqoop2
    juju add-relation sqoop2 jdk
    juju add-relation sqoop2 plugin
    juju expose sqoop2


You can now ssh into the instance using:
`juju ssh sqoop2/0`
and execute sqoop commands.


## Verify the deployment

### Status and Smoke Test

The services provide extended status reporting to indicate when they are ready:

    juju status

This is particularly useful when combined with `watch` to track the on-going
progress of the deployment:

    watch -n 0.5 juju status

The message for each unit will provide information about that unit's state.
Once they all indicate that they are ready, you can perform a "smoke test"
to verify that Sqoop is working as expected using the built-in `smoke-test`
action:

    juju run-action sqoop2/0 smoke-test

_**Note**: The above assumes Juju 2.0 or greater. If using an earlier version
of Juju, the syntax is `juju action do hbase/0 smoke-test`._

After a few seconds or so, you can check the results of the smoke test:

    juju show-action-status

_**Note**: The above assumes Juju 2.0 or greater. If using an earlier version
 +of Juju, the syntax is `juju action status`._

You will see `status: completed` if the smoke test was successful, or
`status: failed` if it was not.  You can get more information on why it failed
via:

    juju show-action-output <action-id>

_**Note**: The above assumes Juju 2.0 or greater. If using an earlier version
 +of Juju, the syntax is `juju action fetch <action-id>`._


## Contact Information

- <bigdata@lists.ubuntu.com>


## Help

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
