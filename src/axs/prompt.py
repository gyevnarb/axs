""" This module contains the prompt generator functions for the LLM. """


class Prompt:
    """ A class to generate prompts from templates and context.
    The template should be specified with placeholders for the context variables
    such that they can be formatted using the `str.format` method."""

    def __init__(self, template: str, time: int = None):
        """ Initialize the Prompt with the template with an
        optional time step for when it becomes valid.

        Args:
            template (str): The template string with placeholders for context variables.
            time (int): The time step when the prompt becomes valid
        """
        self.template = template
        self.time = time

    def fill(self, **context) -> str:
        """ Complete the prompt from the template and context. """
        return self.template.format(**context)
