"""Provides a convenience class for using various LLM models.

Supports offline, localhost, and online LLM models.
"""

import logging

import openai
from vllm import SamplingParams

from axs.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMWrapper:
    """A convenience class for using locally hosted, offline, or online LLM models."""

    def __init__(self, config: LLMConfig) -> "LLMWrapper":
        """Initialize the LLMWrapper with the configuration.

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
            from vllm import LLM
            self._llm = LLM(
                config.model,
                seed=self._sampling_params.seed,
                **config.model_kwargs,
            )
        elif self._mode == "localhost":
            base_url = config.base_url
            if not base_url:
                base_url = "http://localhost:8000/v1"
            self._llm = openai.OpenAI(api_key="EMPTY", base_url=base_url)
        elif self._mode == "online":
            if not config.base_url:
                self._llm = openai.OpenAI()
            else:
                self._llm = openai.OpenAI(base_url=config.base_url)
        else:
            error_msg = f"Invalid inference mode: {self._mode}"
            raise ValueError(error_msg)

    def chat(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Chat with the LLM model using the given messages.

        Args:
            messages (List[Dict[str, str]]): List of messages to send to the LLM model.

        """
        logger.debug(
            "[bold yellow]Latest message:[/bold yellow]\n%s", messages[-1]["content"],
            extra={"markup": True},
        )

        if self._mode == "offline":
            outputs = self._llm.chat(messages, sampling_params=self._sampling_params)
            return [
                {"role": "assistant", "content": ot.outputs[0].text} for ot in outputs
            ]

        available_models = [m.id for m in self._llm.models.list().data]
        internal_name = [
            model for model in available_models if self.config.model in model
        ]
        if not internal_name:
            error_msg = (
                f"Model {self.config.model} not found in openai.OpenAI "
                f"available models: {available_models}"
            )
            raise ValueError(error_msg)
        if len(internal_name) > 1:
            error_msg = (
                f"Multiple models found for {self.config.model}: {internal_name}"
            )
            raise ValueError(error_msg)
        completions = self._llm.chat.completions.create(
            model=internal_name[0],
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
            top_p=self._sampling_params.top_p,
        )
        responses = [
            {"role": c.message.role, "content": c.message.content}
            for c in completions.choices
        ]

        logger.debug(
            "[bold yellow]LLM response:[/bold yellow]\n%s", responses[0]["content"],
            extra={"markup": True},
        )
        return responses

    @property
    def mode(self) -> str:
        """Get the current inference mode."""
        return self._mode
