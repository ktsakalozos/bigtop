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

### Apache Alluxio

Is a memory-centric distributed storage system that bridges
applications and underlying storage systems providing
unified data access orders of magnitudes faster than
existing solutions

## Deployment

This charm deployes Apache Alluxio as packaged by Apache Bigtop.

Alluxio deployment follows a master-workers architecture.
There is always one master that Juju selects automatically for you.
Should the selected master fail Juju will select another master to take its place.
The unit acting as master can be identified by its status message that reads
`ready - master`.

Note that the current charm does not set up a highly available cluster,
meaning that losing the master will affect any files in a transient state.

To deploy Alluxio charm you just need to:

    juju deploy alluxio
    juju deploy openjdk
    juju add-relation alluxio openjdk

And then scale the deployment to your needs

    juju add-unit -n 3 alluxio


## Usage

After all units are in the `ready` state you can login
to an alluxio unit and interact with the filesystem as descirbed in the
Alluxio [Quick Start Guide] (http://www.alluxio.org/docs/master/en/Getting-Started.html)

## Verify the deployment

### Status and Smoke Test
The services provide extended status reporting to indicate when they are ready:

    juju status

This is particularly useful when combined with `watch` to track the on-going
progress of the deployment:

    watch -n 0.5 juju status

The message for each unit will provide information about that unit's state.
Once they all indicate that they are ready, you can perform a "smoke test"
to verify that Alluxio is working as expected using the built-in `smoke-test`
action:

    juju run-action alluxio/0 smoke-test

_**Note**: The above assumes Juju 2.0 or greater. If using an earlier version
of Juju, the syntax is `juju action do alluxio/0 smoke-test`._

After a minute or so, you can check the results of the smoke test:

    juju show-action-status

_**Note**: The above assumes Juju 2.0 or greater. If using an earlier version
of Juju, the syntax is `juju action status`._

You will see `status: completed` if the smoke test was successful, or
`status: failed` if it was not.  You can get more information on why it failed
via:

    juju show-action-output <action-id>

_**Note**: The above assumes Juju 2.0 or greater. If using an earlier version
of Juju, the syntax is `juju action fetch <action-id>`._


## Contact Information

- <bigdata@lists.ubuntu.com>


## Help

- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
