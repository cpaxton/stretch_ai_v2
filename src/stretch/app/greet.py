#!/usr/bin/env python3

# Copyright (c) Hello Robot, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in the root directory
# of this source tree.
#
# Some code may be adapted from other open-source works with their respective licenses. Original
# license information maybe found below, if so.

import stretch.utils.logger as logger
from stretch.agent.operations import WaveOperation
from stretch.agent.robot_agent import RobotAgent
from stretch.agent.zmq_client import HomeRobotZmqClient
from stretch.core import get_parameters


def main(
    robot_ip: str = "",
    local: bool = False,
    parameter_file: str = "default_planner.yaml",
):
    # Create robot client
    parameters = get_parameters(parameter_file)
    robot = HomeRobotZmqClient(
        robot_ip=robot_ip,
        use_remote_computer=(not local),
        parameters=parameters,
    )

    robot.move_to_nav_posture()

    # create robot agent
    demo = RobotAgent(robot, parameters=parameters)

    wave = WaveOperation("emote", robot=robot)
    res = wave()
    if not res:
        logger.error("Wave operation failed")

    # Turn off the robot at the end
    robot.stop()


if __name__ == "__main__":
    main()