#!/usr/bin/env python3

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


import unittest
import amulet


class TestDeploy(unittest.TestCase):
    """
    Trivial deployment test for Apache Sqoop 2.
    """

    @classmethod
    def setUpClass(cls):
        cls.d = amulet.Deployment(series='trusty')
        cls.d.add('sqoop2', 'sqoop2')
        cls.d.add('namenode', 'hadoop-namenode')
        cls.d.add('resourcemanager', 'hadoop-resourcemanager')
        cls.d.add('slave', 'hadoop-slave')
        cls.d.add('plugin', 'hadoop-plugin')
        cls.d.add('openjdk', 'openjdk')

        cls.d.relate('plugin:hadoop-plugin', 'sqoop2:hadoop')
        cls.d.relate('plugin:resourcemanager', 'resourcemanager:resourcemanager')
        cls.d.relate('plugin:namenode', 'namenode:namenode')
        cls.d.relate('slave:namenode', 'namenode:datanode')
        cls.d.relate('slave:resourcemanager', 'resourcemanager:nodemanager')
        cls.d.relate('resourcemanager:namenode', 'namenode:namenode')

        cls.d.relate('sqoop2:java', 'openjdk:java')
        cls.d.relate('plugin:java', 'openjdk:java')
        cls.d.relate('namenode:java', 'openjdk:java')
        cls.d.relate('resourcemanager:java', 'openjdk:java')
        cls.d.relate('slave:java', 'openjdk:java')

        cls.d.setup(timeout=1800)
        cls.d.sentry.wait(timeout=1800)

    def test_deploy(self):
        self.d.sentry.wait_for_messages({"sqoop2": "ready"})
        sqoop2 = self.d.sentry['sqoop2'][0]
        smk_uuid = sqoop2.action_do("smoke-test")
        output = self.d.get_action_output(smk_uuid)
        assert "success" in output['outcome']


if __name__ == '__main__':
    unittest.main()
