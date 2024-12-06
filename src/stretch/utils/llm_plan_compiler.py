# Copyright (c) Hello Robot, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in the root directory
# of this source tree.
#
# Some code may be adapted from other open-source works with their respective licenses. Original
# license information maybe found below, if so.

import ast

from stretch.agent.operations import (
    GoToNavOperation,
    GraspObjectOperation,
    NavigateToObjectOperation,
    PlaceObjectOperation,
    PreGraspObjectOperation,
    SearchForObjectOnFloorOperation,
    SearchForReceptacleOperation,
    SetCurrentObjectOperation,
    SpeakOperation,
    WaveOperation,
)
from stretch.agent.robot_agent import RobotAgent
from stretch.core.task import Task


class LLMTreeNode:
    """Represents a node in the tree of function calls.
    Each node has a function call and two branches for success and failure"""

    def __init__(self, function_call, success=None, failure=None):
        self.function_call = function_call
        self.success = success
        self.failure = failure


class LLMPlanCompiler(ast.NodeVisitor):
    def __init__(self, agent: RobotAgent, llm_plan: str):
        self.agent = agent
        self.robot = agent.robot
        self.llm_plan = llm_plan
        self.task = None
        self.root = None
        self._operation_naming_counter = 0

    def go_to(self, location: str):
        """Adds a GoToNavOperation to the task"""
        _, current_object = self.agent.get_instance_from_text(location)

        if current_object is not None:
            print(f"Setting current object to {current_object}")
            set_current_object = SetCurrentObjectOperation(
                name="set_current_object_" + location + f"_{str(self._operation_naming_counter)}",
                agent=self.agent,
                robot=self.robot,
                target=current_object,
            )
            self._operation_naming_counter += 1
            self.task.add_operation(set_current_object, True)

        go_to = NavigateToObjectOperation(
            name="go_to_" + location + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
            to_receptacle=False,
        )
        self._operation_naming_counter += 1
        go_to.configure(location=location)
        self.task.add_operation(go_to, True)

        if current_object is not None:
            self.task.connect_on_success(set_current_object.name, go_to.name)
            return (
                "set_current_object_" + location + f"_{str(self._operation_naming_counter - 2)}",
                "go_to_" + location + f"_{str(self._operation_naming_counter - 1)}",
            )
        return "go_to_" + location + f"_{str(self._operation_naming_counter - 1)}"

    def pick(self, object_name: str):
        """Adds a GraspObjectOperation to the task"""
        # Try to expand the frontier and find an object; or just wander around for a while.

        go_to_navigation_mode = GoToNavOperation(
            name="go_to_navigation_mode" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            retry_on_failure=True,
        )
        self._operation_naming_counter += 1

        search_for_object = SearchForObjectOnFloorOperation(
            name=f"search_for_{object_name}_on_floor" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            retry_on_failure=True,
            match_method="feature",
            require_receptacle=False,
        )
        self._operation_naming_counter += 1
        search_for_object.set_target_object_class(object_name)

        go_to_object = NavigateToObjectOperation(
            name="go_to_object" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            parent=search_for_object,
            on_cannot_start=search_for_object,
            to_receptacle=False,
        )
        self._operation_naming_counter += 1

        pregrasp_object = PreGraspObjectOperation(
            name="pregrasp_" + object_name + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
            on_failure=None,
            retry_on_failure=True,
        )
        self._operation_naming_counter += 1

        grasp_object = GraspObjectOperation(
            name="pick_" + object_name + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
            on_failure=pregrasp_object,
        )
        self._operation_naming_counter += 1
        grasp_object.configure(
            target_object=object_name, show_object_to_grasp=False, show_servo_gui=False
        )
        grasp_object.set_target_object_class(object_name)
        grasp_object.servo_to_grasp = True
        grasp_object.match_method = "feature"

        self.task.add_operation(go_to_navigation_mode, True)
        self.task.add_operation(search_for_object, True)
        self.task.add_operation(go_to_object, True)
        self.task.add_operation(pregrasp_object, True)
        self.task.add_operation(grasp_object, True)

        self.task.connect_on_success(go_to_navigation_mode.name, search_for_object.name)
        self.task.connect_on_success(search_for_object.name, go_to_object.name)
        self.task.connect_on_success(go_to_object.name, pregrasp_object.name)
        self.task.connect_on_success(pregrasp_object.name, grasp_object.name)

        return (
            go_to_navigation_mode.name,
            grasp_object.name,
        )

    def place(self, receptacle_name: str):
        """Adds a PlaceObjectOperation to the task"""
        go_to_navigation_mode = GoToNavOperation(
            name="go_to_navigation_mode" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            retry_on_failure=True,
        )
        self._operation_naming_counter += 1

        search_for_receptacle = SearchForReceptacleOperation(
            name=f"search_for_{receptacle_name}" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            retry_on_failure=True,
            match_method="feature",
        )
        self._operation_naming_counter += 1
        search_for_receptacle.set_target_object_class(receptacle_name)

        go_to_receptacle = NavigateToObjectOperation(
            name="go_to_receptacle" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            parent=search_for_receptacle,
            on_cannot_start=search_for_receptacle,
            to_receptacle=True,
        )
        self._operation_naming_counter += 1

        place_object_on_receptacle = PlaceObjectOperation(
            name="place_" + receptacle_name + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
            on_cannot_start=go_to_receptacle,
            require_object=True,
        )
        self._operation_naming_counter += 1

        self.task.add_operation(go_to_navigation_mode, True)
        self.task.add_operation(search_for_receptacle, True)
        self.task.add_operation(go_to_receptacle, True)
        self.task.add_operation(place_object_on_receptacle, True)

        self.task.connect_on_success(go_to_navigation_mode.name, search_for_receptacle.name)
        self.task.connect_on_success(search_for_receptacle.name, go_to_receptacle.name)
        self.task.connect_on_success(go_to_receptacle.name, place_object_on_receptacle.name)

        return (
            go_to_navigation_mode.name,
            place_object_on_receptacle.name,
        )

    def say(self, message: str):
        """Adds a SpeakOperation to the task"""
        say_operation = SpeakOperation(
            name="say_" + message + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
        )
        self._operation_naming_counter += 1
        say_operation.configure(message=message)
        self.task.add_operation(say_operation, True)
        return "say_" + message + f"_{str(self._operation_naming_counter - 1)}"

    def wave(self):
        """Adds a WaveOperation to the task"""
        self.task.add_operation(
            WaveOperation(
                name="wave" + f"_{str(self._operation_naming_counter)}",
                agent=self.agent,
                robot=self.robot,
            ),
            True,
        )
        self._operation_naming_counter += 1
        return "wave" + f"_{str(self._operation_naming_counter - 1)}"

    def open_cabinet(self):
        """Adds a SpeakOperation (not implemented) to the task"""
        speak_not_implemented = SpeakOperation(
            name="open_cabinet" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
        )
        self._operation_naming_counter += 1
        speak_not_implemented.configure(message="Open cabinet operation not implemented")
        self.task.add_operation(speak_not_implemented, True)
        return "open_cabinet" + f"_{str(self._operation_naming_counter - 1)}"

    def close_cabinet(self):
        """Adds a SpeakOperation (not implemented) to the task"""
        speak_not_implemented = SpeakOperation(
            name="close_cabinet" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
        )
        self._operation_naming_counter += 1
        speak_not_implemented.configure(message="Close cabinet operation not implemented")
        self.task.add_operation(speak_not_implemented, True)
        return "close_cabinet" + f"_{str(self._operation_naming_counter - 1)}"

    def get_detections(self):
        """Adds a SpeakOperation (not implemented) to the task"""
        speak_not_implemented = SpeakOperation(
            name="get_detections" + f"_{str(self._operation_naming_counter)}",
            agent=self.agent,
            robot=self.robot,
        )
        self._operation_naming_counter += 1
        speak_not_implemented.configure(message="Get detections operation not implemented")
        self.task.add_operation(speak_not_implemented, True)
        return "get_detections" + f"_{str(self._operation_naming_counter - 1)}"

    def build_tree(self, node, parent_success=None, parent_failure=None):
        """Recursively build a tree of function calls and connect nested logic."""
        if isinstance(node, ast.If):
            # Extract function call in the test condition
            test = node.test
            if isinstance(test, ast.Call):
                function_call = ast.unparse(test)
            else:
                raise ValueError("Unexpected test condition")

            # Create the new node for this `if`
            new_node = LLMTreeNode(function_call=function_call)

            # Set the root if it hasn't been set yet
            if self.root is None:
                self.root = new_node

            # Attach to parent's success or failure context
            if parent_success and not parent_success.success:
                parent_success.success = new_node
            if parent_failure and not parent_failure.failure:
                parent_failure.failure = new_node

            # Initialize pointers to the last processed nodes for success and failure
            last_success = new_node
            last_failure = new_node

            # Recursively process the `body` for success
            for expr in node.body:
                last_success = self.build_tree(expr, parent_success=last_success)

            # Recursively process the `orelse` for failure
            for expr in node.orelse:
                last_failure = self.build_tree(expr, parent_failure=last_failure)

            return new_node

        elif isinstance(node, ast.Expr):
            # Handle function calls directly
            expr = node.value
            if isinstance(expr, ast.Call):
                function_call = ast.unparse(expr)
                leaf_node = LLMTreeNode(function_call=function_call)

                # Set the root if it hasn't been set yet
                if self.root is None:
                    self.root = leaf_node

                # Attach to parent's success/failure context if provided
                if parent_success and not parent_success.success:
                    parent_success.success = leaf_node
                elif parent_failure and not parent_failure.failure:
                    parent_failure.failure = leaf_node

                return leaf_node

        elif isinstance(node, ast.Module):
            # Process the top-level module body
            last_node = None
            for expr in node.body:
                last_node = self.build_tree(expr, parent_success=last_node)
            return last_node

        elif isinstance(node, ast.FunctionDef):
            # Process the body of a function definition
            last_node = None
            for expr in node.body:
                last_node = self.build_tree(expr, parent_success=last_node)

            # Set the root if it hasn't been set yet
            if self.root is None and last_node:
                self.root = last_node

            return last_node

        else:
            # Handle unexpected nodes gracefully
            print(f"Unknown node type: {type(node)}")
            return None

    def convert_to_task(
        self, root: LLMTreeNode, parent_operation_name: str = None, success: bool = True
    ):
        """Recursively convert the tree into a task by adding operations and connecting them"""
        if root is None:
            return

        # Create the operation
        operation_ret = eval("self." + root.function_call)

        intermediate_operation_name = None

        if type(operation_ret) is tuple:
            root_operation_name = operation_ret[1]
            intermediate_operation_name = operation_ret[0]
        else:
            root_operation_name = operation_ret

        # root_operation_name

        # Connect the operation to the parent
        if parent_operation_name is not None:
            if success:
                # self.task.connect_on_success(parent_operation_name, root_operation_name)
                if intermediate_operation_name is not None:
                    self.task.connect_on_success(parent_operation_name, intermediate_operation_name)
                    # self.task.connect_on_success(intermediate_operation_name, root_operation_name)

                    self.task.connect_on_failure(intermediate_operation_name, parent_operation_name)
                    self.task.connect_on_failure(root_operation_name, parent_operation_name)
                else:
                    self.task.connect_on_success(parent_operation_name, root_operation_name)
                    self.task.connect_on_failure(root_operation_name, parent_operation_name)
            else:
                # self.task.connect_on_failure(parent_operation_name, root_operation_name)
                if intermediate_operation_name is not None:
                    self.task.connect_on_failure(parent_operation_name, intermediate_operation_name)
                    # self.task.connect_on_success(intermediate_operation_name, root_operation_name)

                    self.task.connect_on_failure(intermediate_operation_name, parent_operation_name)
                    self.task.connect_on_failure(root_operation_name, parent_operation_name)

                    # intermediate_operation = self.task.get_operation(intermediate_operation_name)
                    # intermediate_operation.on_failure = self.task.get_operation(parent_operation_name)

                    # root_operation = self.task.get_operation(root_operation_name)
                    # root_operation.on_failure = self.task.get_operation(parent_operation_name)
                else:
                    self.task.connect_on_failure(parent_operation_name, root_operation_name)
                    self.task.connect_on_failure(root_operation_name, parent_operation_name)

        # Recursively process the success and failure branches
        self.convert_to_task(root.success, root_operation_name, True)
        self.convert_to_task(root.failure, root_operation_name, False)

    def compile(self):
        """Compile the LLM plan into a task"""
        self._operation_naming_counter = 0
        self.task = Task()

        llm_plan_lines = self.llm_plan.split("\n")

        llm_plan_lines_shifted = [llm_plan_lines[0]]
        llm_plan_lines_shifted.append("    if say('On it!'):")
        for line in llm_plan_lines[1:]:
            llm_plan_lines_shifted.append("    " + line)

        self.llm_plan = "\n".join(llm_plan_lines_shifted)

        tree = ast.parse(self.llm_plan)
        self.build_tree(tree)
        self.convert_to_task(self.root)

        return self.task
