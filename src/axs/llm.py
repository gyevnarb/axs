""" This module provides a convenience class for using
locally hosted, offline, or online LLM models. """
import logging
from typing import Dict, List

import openai
from vllm import LLM, SamplingParams

from axs.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMWrapper:
    """ A convenience class for using locally hosted, offline, or online LLM models. """

    def __init__(self, config: LLMConfig):
        """ Initialize the LLMWrapper with the configuration.

        Args:
            config (LLMConfig): The configuration object for the LLMWrapper.
        """
        self.config = config

        self._llm = None
        if "stop" not in config.sampling_params:
            config.sampling_params["stop"] = ["<|endoftext|>"]
        self._sampling_params = SamplingParams(**config.sampling_params)
        self._mode = config.inference_mode

        if self._mode == "offline":
            self._llm = LLM(config.model,
                            seed=self._sampling_params.seed,
                            **config.model_kwargs)
        elif self._mode == "localhost":
            self._llm = openai.OpenAI(api_key = "EMPTY",
                                      base_url = "http://localhost:8000/v1")
        elif self._mode == "online":
            self._llm = openai.OpenAI()
        else:
            raise ValueError(f"Invalid inference mode: {self._mode}")

    def chat(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """ Chat with the LLM model using the given messages.

        Args:
            messages (List[Dict[str, str]]): The list of messages to send to the LLM model.
        """
        if self._mode == "offline":
            outputs = self._llm.chat(messages, sampling_params=self._sampling_params)
            return [{"role": "assistant", "content": ot.outputs[0].text}
                    for ot in outputs]
        else:
            completions = self._llm.chat.completions.create(
                model=self.config.model,
                messages=messages,
                stream=False,
                seed=self._sampling_params.seed,
                n=self._sampling_params.n,
                logit_bias=self._sampling_params.logit_bias,
                logprobs=self._sampling_params.logprobs,
                max_tokens=self._sampling_params.max_tokens,
                presence_penalty=self._sampling_params.presence_penalty,
                frequency_penalty=self._sampling_params.frequency_penalty,
                stop=self._sampling_params.stop,
                temperature=self._sampling_params.temperature,
                top_p=self._sampling_params.top_p)
            return [{"role": c.message.role, "content": c.message.content}
                     for c in completions.choices]

    @property
    def mode(self) -> str:
        """ Get the current inference mode. """
        return self._mode
