"""Contains functions for wrapping low-level actions to higher level abstractions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from axs.config import MacroActionConfig, Registerable, SupportedEnv


@dataclass
class ActionSegment:
    """A segment of the same repeated actions with corresponding times.

    Attributes:
        times (list[int]): The timesteps of the actions.
        actions (list[Any]): The actions taken during the timesteps.
        name (Tuple[str]): The name of the action segment.

    """

    times: list[int]
    actions: list[Any]
    name: tuple[str, ...]

    def __post_init__(self) -> None:
        """Check if the lengths of times and actions are equal."""
        if len(self.times) != len(self.actions):
            error_msg = (
                f"Length of times {self.times} and "
                f"actions {self.actions} must be equal."
            )
            raise ValueError(error_msg)


_macro_library: dict[str, "type[MacroAction]"] = {}

class MacroAction(ABC, Registerable, class_type=None):
    """Abstract base class for macro actions.

    Attributes:
        macro_names (list[str]): The names of the macro actions.

    """

    macro_names: ClassVar[list[str]] = []

    def __init__(
        self, name: str, action_segments: list[ActionSegment],
    ) -> "MacroAction":
        """Initialize the macro action with an empty list of actions.

        This method also checks whether the macro library has been defined.

        Args:
            name (str): The name of the macro action.
            action_segments (list[ActionSegment]): Action segments of the macro action.

        """
        if not self.macro_names:
            error_msg = f"Macro library of {type(self)} is empty."
            raise ValueError(error_msg)
        if name not in self.macro_names:
            error_msg = (
                f"Macro action {name} not found in the factory with {self.macro_names}."
            )
            raise ValueError(error_msg)
        self.macro_name = name

        if any(not isinstance(seg, ActionSegment) for seg in action_segments):
            error_msg = (
                f"Action segments {action_segments} must be of type ActionSegment."
            )
            raise ValueError(error_msg)
        self.action_segments = action_segments
        self.__repr__()  # Call repr to check if it is implemented

    def __repr__(self) -> str:
        """Return representation of the macro action. Used in verbalization."""
        error_msg = "MacroAction __repr__ must be overriden."
        raise RuntimeError(error_msg)

    @classmethod
    @abstractmethod
    def wrap(
        cls,
        config: MacroActionConfig,
        env: SupportedEnv,
        actions: list[Any],
        observations: list[Any],
        infos: list[dict[str, Any]] | None = None,
    ) -> dict[int, list["MacroAction"]]:
        """Wrap low-level actions, observations, or other infos into macro actions.

        Wrapping is done for each agent present in the data.
        For simple action spaces, this function may just return the actions as they are.
        The actions within a macro action are grouped into ActionSegments.

        Args:
            config (MacroActionConfig): Configuration for the macro action.
            env (SupportedEnv): Environment for the agent.
            actions (list[Any]): Low-level trajectory of actions of the agent to wrap.
            observations (list[Any]): Environment observation sequence.
            infos (list[dict[str, Any]] | None): list of info dictionaries from the env.

        Returns:
            Dict[int, list[MacroAction]]: A dictionary of agent ids to macro actions.

        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def unwrap(cls, macro_actions: list["MacroAction"]) -> list[Any]:
        """Unwrap the macro actions into low-level actions.

        Args:
            macro_actions (list[MacroAction]): Macro actions to unwrap.

        """
        raise NotImplementedError

    @property
    def start_t(self) -> int:
        """The start time of the macro action."""
        return self.action_segments[0].times[0]

    @property
    def end_t(self) -> int:
        """The end time of the macro action."""
        return self.action_segments[-1].times[-1]
