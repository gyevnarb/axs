"""Get all combinations of experimetal conditions."""

import json
import logging
from collections.abc import Iterable
from copy import deepcopy
from itertools import chain, combinations
from pathlib import Path

import axs

logger = logging.getLogger(__name__)


def get_agent(config: axs.Config) -> axs.AXSAgent:
    """Create an AXS agent with the given configuration."""
    env = axs.util.load_env(config.env, config.env.render_mode)
    env.reset(seed=config.env.seed)
    logger.info("Created environment %s", config.env.name)

    agent_policies = axs.registry.get(config.env.policy_type).create(env)
    return axs.AXSAgent(config, agent_policies)


def powerset(iterable: Iterable) -> list[tuple]:
    """Generate the powerset of a given iterable.

    Args:
        iterable (Iterable): The input iterable.

    """
    s = list(iterable)
    # Change iteration to range(1, len(s)+1) to exclude empty set
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))


def get_configs(
    scenarios: list[int],
    complexity: list[int],
    models: list[str],
    use_interrogation: bool,
    use_context: bool,
    n_max: int,
) -> list[axs.Config]:
    """Get all combinations of experimetal conditions."""
    if not use_interrogation and not use_context:
        error_msg = "At least one of use_interrogation or use_context must be True."
        raise ValueError(error_msg)

    verbalizer_features = [
        "add_layout",
        "add_observations",
        "add_actions",
        "add_macro_actions",
    ]
    with Path("scripts", "python", "llm-configs.json").open() as f:
        llm_configs = json.load(f)
    sampling_params = llm_configs.pop("sampling_params")
    llm_configs = {k: v for k, v in llm_configs.items() if k in models}

    configs = []
    for scenario in scenarios:
        with Path("data", "igp2", "configs", f"scenario{scenario}.json").open() as f:
            config_dict = json.load(f)

        config_dict["llm"]["sampling_params"].update(sampling_params)
        config_dict["axs"]["use_interrogation"] = use_interrogation
        config_dict["axs"]["use_context"] = use_context
        config_dict["axs"]["n_max"] = n_max

        # Create LLM config combinations
        for llm_config in llm_configs.values():
            for c in complexity:
                for vf in powerset(verbalizer_features):
                    new_config_dict = deepcopy(config_dict)
                    new_config_dict["axs"]["complexity"] = c
                    new_config_dict["llm"].update(llm_config)
                    if "add_actions" not in vf and "add_macro_actions" not in vf:
                        continue
                    if use_context and vf != ():
                        new_config_dict["axs"]["verbalizer"]["params"] = {
                            k: True for k in vf
                        }
                        params = {
                            "complexity": c,
                            "verbalizer_features": vf,
                            "llm_config": llm_config,
                            "scenario": scenario,
                            "use_interrogation": use_interrogation,
                            "use_context": use_context,
                            "n_max": n_max,
                            "config": axs.Config(new_config_dict),
                        }
                        configs.append(params)
                    elif not use_context and vf == ():
                        new_config_dict["axs"]["verbalizer"]["params"] = {
                            k: False for k in verbalizer_features
                        }
                        params = {
                            "complexity": c,
                            "verbalizer_features": vf,
                            "llm_config": llm_config,
                            "scenario": scenario,
                            "use_interrogation": use_interrogation,
                            "use_context": use_context,
                            "n_max": n_max,
                            "config": axs.Config(new_config_dict),
                        }
                        configs.append(params)
                        break
    return configs
