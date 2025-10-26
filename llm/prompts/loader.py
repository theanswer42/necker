"""Prompt loading and management."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from logger import get_logger

logger = get_logger()


class PromptManager:
    """Manages loading and rendering of prompts from YAML files."""

    def __init__(self, prompts_dir: Optional[Path] = None):
        """Initialize the prompt manager.

        Args:
            prompts_dir: Directory containing prompt YAML files.
                        Defaults to llm/prompts/ in the project.
        """
        if prompts_dir is None:
            # Default to llm/prompts directory
            self.prompts_dir = Path(__file__).parent
        else:
            self.prompts_dir = prompts_dir

        self._cache: Dict[str, Dict[str, Any]] = {}

    def load_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """Load a prompt configuration from YAML file.

        Args:
            prompt_name: Name of the prompt file (without .yaml extension).

        Returns:
            Dictionary containing prompt configuration.

        Raises:
            FileNotFoundError: If prompt file doesn't exist.
            yaml.YAMLError: If YAML is invalid.
        """
        # Check cache first
        if prompt_name in self._cache:
            return self._cache[prompt_name]

        prompt_file = self.prompts_dir / f"{prompt_name}.yaml"

        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        logger.info(f"Loading prompt from {prompt_file}")

        with open(prompt_file, "r") as f:
            prompt_config = yaml.safe_load(f)

        # Cache the loaded prompt
        self._cache[prompt_name] = prompt_config

        return prompt_config

    def render_prompt(
        self, prompt_name: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Load and render a prompt with the given variables.

        Args:
            prompt_name: Name of the prompt to load.
            variables: Dictionary of variables to substitute in templates.

        Returns:
            Dictionary with rendered prompts and parameters.
            Keys: system_prompt, user_prompt, parameters
        """
        prompt_config = self.load_prompt(prompt_name)

        # Render templates
        system_prompt = prompt_config.get("system_prompt", "")
        user_prompt_template = prompt_config.get("user_prompt_template", "")

        # Simple string formatting for now
        # Could upgrade to Jinja2 if we need more complex templates later
        user_prompt = user_prompt_template.format(**variables)

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "parameters": prompt_config.get("parameters", {}),
            "version": prompt_config.get("version", "unknown"),
        }
