"""Verbalize IGP2 simulation data."""

import itertools
import logging
from collections import defaultdict
from typing import Any

import gofi
import igp2 as ip
import numpy as np
from shapely import Polygon

import axs
from envs.axs_igp2 import util
from envs.axs_igp2.macroaction import IGP2MacroAction

logger = logging.getLogger(__name__)


ROAD_LAYOUT_PRETEXT = """- Metadata:
  - Traffic rules:
    - Vehicles drive on the right side of the road.
    - The maximum speed limit is 10 m/s.
  - Road layout:
    - The road layout consists of roads identified as Road(road ID).
    - Roads are made up of lanes identified as Road(road ID:lane ID).
    - Lanes are divided into left and right lanes.
    - Left lanes have positive lane IDs, while right lanes have negative lane IDs.
"""

REWARD_NAME_MAP = {
    "jerk": "Jolt",
    "coll": "Collision",
    "curvature": "Curvature",
    "term": "Goal-not-reached",
    "angular_velocity": "Steering",
    "time": "Time-to-Goal",
    "dead": "Goal-not-Reached",
}


class IGP2Verbalizer(axs.Verbalizer):
    """Verbalize the environment, observations, and state for IGP2."""

    layout_printed = False

    @staticmethod
    def reset() -> None:
        """Set the layout_printed flag to False."""
        IGP2Verbalizer.layout_printed = False

    @staticmethod
    def convert(
        observations: list[np.ndarray],  # noqa: ARG004
        macro_actions: dict[int, list[IGP2MacroAction]],
        infos: list[dict[str, ip.AgentState]] | None = None,
        rewards: dict[int, ip.Reward] | None = None,
        query: axs.Query | None = None,
        env: ip.simplesim.SimulationEnv | None = None,
        **kwargs: dict[str, Any],
    ) -> dict[str, str]:
        """Verbalize the IGP2 scenario.

        Args:
            observations (list): The observations of the agents. Not used.
            macro_actions (list): The macro actions of the agents.
            infos (list): The information of the agents.
            rewards (dict[str, float] | None): Any rewards to verbalize.
            query (axs.Query | None): The query to verbalize.
            env (ip.simplesim.SimulationEnv | None): The IGP2 environment.
            kwargs: Optional keyword arguments.
                - add_layout: Whether to add the road layout description.
                - add_roads: Whether to add road descriptions.
                - add_metadata: Whether to add metadata before
                            the road layout description.
                - add_buildings: Whether to add building descriptions.
                - add_actions: Whether to add raw steering and acceleration values.
                - add_macro_actions: Whether to add macro action descriptions.
                - add_observations: Whether to add observation descriptions.
                - add_rewards: Whether to add reward descriptions.
                - add_lanes: Whether to add lane descriptions.
                - add_intersections: Whether to add intersection descriptions.
                - add_intersection_links: Whether to add intersection lane link.
                - subsample (int): Frequency of subsampling observations.
                        Use this to decrease the complexity of the verbalization.
                - rounding (int): Number of decimal places to round the values to.
                - state_signals (list[str]): List of control signals to include.
                        Possible values: ["times", "timesteps", "path",
                                          "velocity", "heading", "lanes"].
                        Default is all control signals except time.
                - resolution: The resolution of the road midline (0.01).
                - fps: The frames per second of the simulation (20).

        Returns:
            context (dict[str, str]): Dictionary of verbalized data with keys mapping to
                argument names in a axs.Query objetc

        """
        if not isinstance(macro_actions, dict) and not all(
            isinstance(k, int) for k in macro_actions
        ):
            error_msg = (
                f"Macro actions must be a dictionary with "
                f"int agent ids as keys. Got: {macro_actions}"
            )
            raise ValueError(error_msg)

        if isinstance(rewards, list) and "reward" in infos[-1]:
            rewards = {0: infos[-1].pop("reward")}

        context = ""
        ret = {}

        add_layout = kwargs.get("add_layout", False)
        add_observations = kwargs.get("add_observations", False)
        add_macro_actions = kwargs.get("add_macro_actions", False)
        add_actions = kwargs.get("add_actions", False)
        add_rewards = kwargs.get("add_rewards", False)

        if add_layout and not IGP2Verbalizer.layout_printed:
            add_coordinate_metadata = add_observations
            context += (
                IGP2Verbalizer.convert_environment(
                    env,
                    add_coordinate_metadata,
                    **kwargs,
                )
                + "\n\n"
            )
            IGP2Verbalizer.layout_printed = True

        actions_dict = IGP2Verbalizer._convert_macro_actions(macro_actions)
        infos_dict = IGP2Verbalizer._convert_infos(infos, env.scenario_map, **kwargs)
        if set(actions_dict.keys()) != set(infos_dict.keys()):
            error_msg = "Agent IDs in actions and infos do not match."
            raise ValueError(error_msg)

        add_observations = kwargs.get("add_observations", False)
        add_macro_actions = kwargs.get("add_macro_actions", False)
        add_actions = kwargs.get("add_actions", False)
        add_rewards = kwargs.get("add_rewards", True)

        for aid, info_dict in infos_dict.items():
            context += f"- Vehicle {aid}:\n"
            # if add_observations or add_actions:
            # context += "  - Observations:\n"
            if add_observations:
                for signal, data in info_dict.items():
                    if signal in ["Steering", "Acceleration", "Lanes"]:
                        continue  # Do not include actions here
                    context += f"  - {signal}: {data}\n"
            if add_actions:
                # context += "  - Actions:\n"
                # if not add_observations:
                #     context += f"    - Timesteps: {info_dict['Timesteps']}\n"
                context += f"  - Steering: {info_dict['Steering']}\n"
                context += f"  - Acceleration: {info_dict['Acceleration']}\n"
            if add_macro_actions:
                context += "  - Macro actions (as macro[from-to]): "
                context += f"[{actions_dict[aid]}]\n"
            if add_layout:
                context += f"  - Lane sequence (as Road(...)[from-to]): [{info_dict['Lanes']}]\n"  # noqa: E501
            if (
                add_rewards
                and rewards is not None
                and isinstance(rewards, dict)
                and aid in rewards
            ):
                context += "  - Rewards:\n"
                reward_str = IGP2Verbalizer._convert_reward(
                    rewards[aid], infos, **kwargs,
                )
                context += f"{reward_str}\n"
            context += "\n"
        context = context[:-2]  # Remove trailing newlines

        ret["context"] = context

        if query is not None:
            q_descriptions, q_type_descriptions = IGP2Verbalizer.convert_query(query)
            ret["query_descriptions"] = q_descriptions
            ret["query_type_descriptions"] = q_type_descriptions

        return ret

    @staticmethod
    def convert_rewards(rewards: ip.Reward, **kwargs: dict[str, Any]) -> str:
        """Verbalize the rewards of the agents.

        Args:
            rewards (dict[str, float] | None): Any rewards to verbalize.
            kwargs: Optional keyword arguments.

        """
        ret = "Rewards:\n"
        for agent_id, reward in rewards.items():
            reward_str = IGP2Verbalizer._verbalize_reward(reward, **kwargs)
            ret += f"  Vehicle {agent_id}: {reward_str}\n"
        return ret[:-1]

    @staticmethod
    def _convert_reward(
        reward: ip.Reward,
        infos: list[dict[str, Any]],
        **kwargs: dict[str, Any],
    ) -> str:
        """Verbalize the IGP2 reward class of an agent.

        Args:
            reward (dict[str, float]): The reward to verbalize.
            kwargs: Optional keyword arguments.
                - rounding (int): Number of decimal places to round the values to.
                - exclude_rewards (list[str]): List of reward signals to exclude.

        """
        ret = ""
        for key, value in reward.reward_components.items():
            if key in kwargs.get("exclude_rewards", []) or value is None:
                continue
            reward_name = REWARD_NAME_MAP.get(key, key)
            colliding_agents = []
            if key == "coll":
                ego_box = None
                for info in infos[::-1]:
                    for aid, state in info.items():
                        if aid == 0:
                            ego_box = Polygon(
                                ip.Box(
                                    state.position,
                                    state.metadata.length + 1.0,
                                    state.metadata.width,
                                    state.heading,
                                ).boundary,
                            )
                            continue
                        if ego_box is not None:
                            agent_box = Polygon(
                                ip.Box(
                                    state.position,
                                    state.metadata.length + 1.0,
                                    state.metadata.width,
                                    state.heading,
                                ).boundary,
                            )
                            if ego_box.intersects(agent_box):
                                colliding_agents.append(f"Vehicle {aid}")
                    if colliding_agents:
                        break

            rounded_value = np.round(value, kwargs.get("rounding", 3))
            if colliding_agents:
                colliding_agents = ", ".join(map(str, colliding_agents))
                ret += f"    - {reward_name}: {rounded_value} (with: {colliding_agents})\n"
            else:
                ret += f"    - {reward_name}: {rounded_value}\n"
        return ret[:-1]

    @staticmethod
    def convert_infos(infos: list[dict[str, Any]], **kwargs: dict[str, Any]) -> str:
        """Verbalize a frame of the simulation state.

        Args:
            infos (list[str, dict[Any]]): Sequence of info dictionaries for each agent.
            kwargs: Optional keyword arguments.
                - subsample (int): Frequency of subsampling observations.
                        Use this to decrease the complexity of the verbalization.
                - rounding (int): Number of decimal places to round the values to.
                - state_signals (list[str]): List of control signals to include.
                        Possible values: ["times", "timesteps", "path", "velocity",
                            "acceleration", "heading", "angular_velocity"].
                        Default is all control signals except time.

        """
        ret = "Observations:\n"
        infos_dict = IGP2Verbalizer._convert_infos(infos, **kwargs)
        for agent_id, state_signals in infos_dict.items():
            ret += f"  Vehicle {agent_id}:\n"
            for signal, data in state_signals.items():
                ret += f"    {signal}: {data}\n"
            ret += "\n"
        return ret[:-1]

    @staticmethod
    def _convert_infos(
        infos: dict[int, list[IGP2MacroAction]],
        scenario_map: ip.Map,
        **kwargs: dict[str, Any],
    ) -> dict[int, dict[str, str]]:
        trajectories = defaultdict(list)
        for frame in infos:
            for agent_id, state in frame.items():
                trajectories[agent_id].append(state)

        trajectories = {
            k: ip.StateTrajectory(kwargs.get("fps", 20), v)
            for k, v in trajectories.items()
        }

        ret = {}

        subsample = kwargs.get("subsample", 1)
        rounding = kwargs.get("rounding", 2)
        state_signals = kwargs.get(
            "state_signals",
            ["timesteps", "path", "velocity", "lanes"],
        )
        # We always calculate these as they may be included as part of the actions
        state_signals.extend(["angular_velocity", "acceleration"])
        for agent_id, trajectory in trajectories.items():
            sampled_trajectory = trajectory
            if subsample > 1 and len(trajectory) > subsample:
                start_t = trajectory[0].time
                sampled_trajectory = util.subsample_trajectory(
                    trajectory,
                    start_t,
                    subsample,
                )

            ret[agent_id] = dict(
                [
                    IGP2Verbalizer._verbalize_control_signal(
                        signal,
                        rounding,
                        sampled_trajectory
                        if signal not in ["acceleration", "angular_velocity"]
                        else trajectory,
                        scenario_map,
                    )
                    for signal in state_signals
                ],
            )

        return ret

    @staticmethod
    def convert_observations(observations: list[Any], **kwargs: dict[str, Any]) -> str:  # noqa: ARG004
        """Verbalize the observations of the agents. Not used in IGP2."""
        logger.debug("IGP2 does not use Verbalizer.convert_observations.")
        return ""

    @staticmethod
    def convert_macro_actions(
        macro_actions: dict[int, list[IGP2MacroAction]],
        **kwargs: dict[str, Any],  # noqa: ARG004
    ) -> str:
        """Verbalize the macro actions of the agents."""
        ret = "Actions:\n"
        segments_dict = IGP2Verbalizer._convert_macro_actions(macro_actions)
        for agent_id, segments_str in segments_dict.items():
            ret += f"Vehicle {agent_id}: {segments_str}\n"
        return ret

    @staticmethod
    def _convert_macro_actions(
        macro_actions: dict[int, list[IGP2MacroAction]],
        **kwargs: dict[str, Any],  # noqa: ARG004
    ) -> dict[int, str]:
        ret = {}
        for agent_id, segmentations in macro_actions.items():
            ret[agent_id] = ", ".join(map(repr, segmentations))
        return ret

    @staticmethod
    def convert_environment(
        env: ip.simplesim.SimulationEnv,
        add_coordinate_metadata: bool = False,
        **kwargs: dict[str, Any],
    ) -> str:
        """Verbalize the road layout.

        Args:
            env (ip.simplesim.SimulationEnv): The igp2 environment to verbalize.
            add_coordinate_metadata (bool): Whether to add coordinate metadata
            kwargs: Optional keyword arguments.
                - add_lanes: Whether to add lane descriptions (True).
                - add_intersections: Whether to add intersection descriptions (True).
                - add_intersection_links: Whether to add intersection lane link (False).
                - resolution: The resolution of the road midline (0.01).
                - add_metadata: Whether to add metadata before
                            the road layout description (False).

        Returns:
            A string describing the road layout.

        """
        scenario_map = env.scenario_map
        ret = ""

        add_metadata = kwargs.get("add_metadata", True)
        add_intersections = kwargs.get("add_intersections", False)
        if add_metadata:
            ret += ROAD_LAYOUT_PRETEXT
            if add_coordinate_metadata:
                ret += "  - Coordinate system:\n"
                ret += "    - Distances are in meters.\n"
                ret += "    - Coordinates are on a 2D Cartesian plane.\n"
                ret += "    - Coordinates are written as [x, y].\n"
                ret += "    - Angles are in radians in the range [-pi, pi].\n"
            if add_intersections:
                ret += "  -Intersections:\n"
                ret += "    - Roads are connected by intersections identified as Intersection(intersection ID)\n"  # noqa: E501
                ret += "    - Intersections are made up of connections between anincoming and connecting lanes.\n"  # noqa: E501
                lane_links = kwargs.get("intersection_links", False)
                ret += "    - Connections are written as "
                if not lane_links:
                    ret += "incoming road id->connecting road id.\n"
                else:
                    ret += "incoming road id:lane id->connecting road id:lane id.\n"
            ret += "\n"

        # Describe roads
        if kwargs.get("add_roads", True):
            ret += "- Road layout:\n"
            ret = IGP2Verbalizer._add_verbalized_roads(ret, scenario_map)
            ret = IGP2Verbalizer._add_road_priority(ret, scenario_map)

        # Describe intersections
        if add_intersections:
            for jid, junction in scenario_map.junctions.items():
                ret += f"  - Intersection({jid}):\n"
                for conn in junction.connections:
                    if kwargs.get("add_intersection_links", False):
                        for lane_link in conn.lane_links:
                            ret += f"    - Lane({conn.incoming_road.id}:{lane_link.from_id})"  # noqa: E501
                            ret += (
                                f"->Lane({conn.connecting_road.id}:{lane_link.to_id})\n"
                            )
                    else:
                        ret += f"    - Road({conn.incoming_road.id})->Road({conn.connecting_road.id})\n"  # noqa: E501

        # Verbalize static objects
        if kwargs.get("add_buildings", True):
            if not isinstance(env.unwrapped.simulation.scenario_map, gofi.OMap):
                logger.warning(
                    "Building descriptions are only available for gofi maps.",
                )
            else:
                ret += "\n"
                ret += "- Static objects:\n"
                for obj in scenario_map.objects:
                    if not obj.object_type:
                        continue
                    obj: gofi.StaticObject
                    ret += f"  - {obj.object_type.title()}:\n"
                    ret += f"    - Center: {obj.center}\n"
                    ret += f"    - Boudnary: {util.ndarray2str(obj.boundary_coords[:-1])}\n"  # noqa: E501

        if ret[-1] == "\n":
            ret = ret[:-1]
        return ret

    @staticmethod
    def _add_verbalized_roads(ret: str, scenario_map: ip.Map) -> None:
        for rid, road in scenario_map.roads.items():
            if not road.drivable:
                continue

            ret += f"  - Road({rid}): "
            # ret += f"    - Length: {road.length} m\n"

            # midline = ramer_douglas(
            #     np.array(road.midline.coords),
            #     dist=kwargs.get("resolution", 0.02),
            # )
            # midline = util.ndarray2str(midline)
            # ret += f"    - Midline coordinates: {midline}\n"

            left_lanes = [
                lane
                for lane in road.lanes.lane_sections[0].left_lanes
                if lane.type == ip.LaneTypes.DRIVING
            ]
            right_lanes = [
                lane
                for lane in road.lanes.lane_sections[0].right_lanes
                if lane.type == ip.LaneTypes.DRIVING
            ]

            all_lanes = left_lanes + right_lanes
            if all_lanes:
                lane_str = ", ".join(
                    [f"Road({rid}:{lane.id})" for lane in all_lanes],
                )
                ret += f"{lane_str}\n"

        return ret

    @staticmethod
    def _add_road_priority(ret: str, scenario_map: ip.Map) -> str:
        ret += "  - Priorities:\n"
        groups = defaultdict(list)
        for junction in scenario_map.junctions.values():
            for priority in junction.priorities:
                groups[priority.high_id].append(priority.low_id)
        for high_id, low_ids in groups.items():
            ret += f"    - Road({high_id}) has priority over: "
            ret += ", ".join([f"Road({low_id})" for low_id in low_ids])
            ret += "\n"
        return ret

    @staticmethod
    def _verbalize_control_signal(
        signal: str,
        precision: int,
        trajectory: ip.StateTrajectory,
        scenario_map: ip.Map,
    ) -> tuple[str, str]:
        name = {
            "times": "Time",
            "timesteps": "Timesteps",
            "maneuver": "Maneuvers",
            "macro": "Macro actions",
            "path": "Position",
            "velocity": "Speed",
            "acceleration": "Acceleration",
            "heading": "Heading",
            "angular_velocity": "Steering",
            "lanes": "Lanes",
        }[signal]
        data = None

        if signal == "timesteps":
            timesteps = np.array([s.time for s in trajectory.states])
            data = util.ndarray2str(timesteps)
        elif signal == "lanes":
            lane_seq = []
            times = []
            last_lane = None
            for state in trajectory.states:
                lane = scenario_map.best_lane_at(state.position, state.heading)
                if lane is not None and last_lane != lane:
                    times.append(state.time)
                    lane_seq.append([lane.parent_road.id, lane.id])
                    last_lane = lane
            times = list(itertools.pairwise([*times, state.time]))
            data = []
            for (t_s, t_e), (road_id, lane_id) in zip(
                times,
                lane_seq,
                strict=True,
            ):
                data.append(f"Road({road_id}:{lane_id})[{t_s}-{t_e}]")
            data = ", ".join(data)
        elif signal in ["acceleration", "angular_velocity"]:
            last_action = None
            action_seq = []
            times = []
            eps = 0.01
            for i in range(len(trajectory)):
                action = getattr(trajectory, signal)[i]
                if action > eps:
                    action = {
                        "acceleration": "Accelerate",
                        "angular_velocity": "SteerLeft",
                    }[signal]
                elif action < -eps:
                    action = {
                        "acceleration": "Decelerate",
                        "angular_velocity": "SteerRight",
                    }[signal]
                else:
                    action = {
                        "acceleration": "MaintainSpeed",
                        "angular_velocity": "KeepStraight",
                    }[signal]
                if action != last_action:
                    times.append(trajectory.states[i].time)
                    action_seq.append(action)
                    last_action = action
            times = list(itertools.pairwise([*times, trajectory.states[i].time]))
            data = []
            for (t_s, t_e), action in zip(
                times,
                action_seq,
                strict=True,
            ):
                data.append(f"{action}[{t_s}-{t_e}]")
            data = ", ".join(data)
        elif signal == "maneuver":
            data = [s.maneuver for s in trajectory.states]
        elif signal == "macro":
            data = [s.macro_action for s in trajectory.states]
        elif hasattr(trajectory, signal):
            data = util.ndarray2str(getattr(trajectory, signal), precision)
        else:
            error_msg = f"Unknown control signal: {signal}"
            raise ValueError(error_msg)

        return name, data

    @staticmethod
    def convert_query(query: axs.Query) -> tuple[str, str]:
        """Convert the query to query and type descriptions.

        Args:
            query (axs.Query): The query to convert.

        Returns:
            tuple: The query and its type descriptions.

        """
        q_desc = query.query_descriptions()
        q_type_desc = query.query_type_descriptions()

        query_str = ""
        for query_name, syntax in query.queries().items():
            query_str += f"- '{syntax}': {q_desc[query_name]}\n"
        query_types_str = "\n".join([f"- {k}: {v}" for k, v in q_type_desc.items()])
        return query_str[:-1], query_types_str
