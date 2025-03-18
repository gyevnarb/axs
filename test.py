import os
import sys
import logging

import igp2 as ip
import gymnasium as gym

import axs
from implementations import axs_igp2


logger = logging.getLogger(__name__)
axs.init_logging(["igp2.core.velocitysmoother", "matplotlib"],
                 log_dir="output/logs", log_name="test")

CONFIG_FILE = "data/igp2/configs/scenario1.json"
OUTPUT = "output/"

if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(f"Configuration file not found: {CONFIG_FILE}")
if not os.path.exists(OUTPUT):
    os.makedirs(OUTPUT)

config = axs.Config(CONFIG_FILE)
env = gym.make(config.env.name,
                config=config.env.params,
                render_mode=config.env.render_mode)
observation, info = env.reset(seed=config.env.seed)

# Registr macro action here if necessary
# axs.MacroAction.register(name: str, type: type["MacroAction"])

axs_agent = axs.AXSAgent(config)
if os.path.exists(f"{OUTPUT}/agent.pkl"):
    axs_agent.load_state(f"{OUTPUT}/agent.pkl")
    prompt = axs.Prompt(**config.axs.user_prompts[0])
    user_query = prompt.fill()
    axs_agent.explain(user_query)

for n in range(config.env.n_episodes):
    logger.info("Running episode %d...", n)

    axs_agent.reset()
    ego_agent = info.pop("ego")

    # Execute external environment as normal
    for t in range(config.env.max_iter):
        action = ego_agent.next_action(ip.Observation(info, env.unwrapped.scenario_map))

        # Learning and explanation phase
        axs_agent.semantic_memory.learn(
            observations=observation, actions=action, infos=info)
        for prompt_dict in config.axs.user_prompts:
            prompt = axs.Prompt(**prompt_dict)
            if t > 0 and prompt.time == t - 1:
                axs_agent.save_state(f"{OUTPUT}/agent.pkl")
                sys.exit(1)
                user_query = prompt.fill()
                axs_agent.explain(user_query)

        # Perform environment step
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            logger.info("Episode terminated.")
            observation, info = env.reset(seed=config.env.seed)
            break

env.close()