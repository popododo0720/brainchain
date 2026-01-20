"""
Prompt injection for MCP tools.

Generates tool descriptions and parses tool calls from model output.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from .client import Tool
from .registry import ToolRegistry


@dataclass
class ToolCall:
    """Represents a parsed tool call from model output."""
    name: str
    arguments: dict[str, Any]
    raw_text: str = ""


class PromptInjector:
    """
    Injects tool descriptions into prompts and parses tool calls.

    Formats tools in a way that AI models can understand and use.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        format_style: str = "xml",  # xml, json, markdown
    ):
        """
        Initialize prompt injector.

        Args:
            registry: ToolRegistry with available tools
            format_style: Output format for tool descriptions
        """
        self.registry = registry
        self.format_style = format_style

    def format_tools_section(self, tools: list[Tool] | None = None) -> str:
        """
        Format tools section for injection into prompts.

        Args:
            tools: Optional list of tools (defaults to all available)

        Returns:
            Formatted tools section string
        """
        if tools is None:
            tools = self.registry.get_all_tools_sync()

        if not tools:
            return ""

        if self.format_style == "xml":
            return self._format_xml(tools)
        elif self.format_style == "json":
            return self._format_json(tools)
        else:
            return self._format_markdown(tools)

    def _format_xml(self, tools: list[Tool]) -> str:
        """Format tools as XML."""
        lines = ["<available_tools>"]

        for tool in tools:
            lines.append(f"  <tool name=\"{tool.name}\">")
            lines.append(f"    <description>{tool.description}</description>")
            if tool.input_schema:
                lines.append(f"    <parameters>{json.dumps(tool.input_schema)}</parameters>")
            lines.append("  </tool>")

        lines.append("</available_tools>")
        lines.append("")
        lines.append("To use a tool, respond with:")
        lines.append("<tool_call>")
        lines.append('  <name>tool_name</name>')
        lines.append('  <arguments>{"arg1": "value1"}</arguments>')
        lines.append("</tool_call>")

        return "\n".join(lines)

    def _format_json(self, tools: list[Tool]) -> str:
        """Format tools as JSON."""
        tools_data = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            }
            for tool in tools
        ]

        return json.dumps({
            "available_tools": tools_data,
            "usage": "To call a tool, include a JSON block: {\"tool\": \"name\", \"arguments\": {...}}"
        }, indent=2)

    def _format_markdown(self, tools: list[Tool]) -> str:
        """Format tools as Markdown."""
        lines = ["## Available Tools\n"]

        for tool in tools:
            lines.append(f"### {tool.name}")
            lines.append(f"{tool.description}\n")
            if tool.input_schema:
                lines.append("**Parameters:**")
                lines.append(f"```json\n{json.dumps(tool.input_schema, indent=2)}\n```\n")

        lines.append("## Tool Usage")
        lines.append("To call a tool, use the following format:")
        lines.append("```")
        lines.append("TOOL_CALL: tool_name")
        lines.append('ARGUMENTS: {"arg1": "value1"}')
        lines.append("```")

        return "\n".join(lines)

    def parse_tool_calls(self, output: str) -> list[ToolCall]:
        """
        Parse tool calls from model output.

        Supports multiple formats:
        - XML: <tool_call><name>...</name><arguments>...</arguments></tool_call>
        - JSON: {"tool": "...", "arguments": {...}}
        - Markdown: TOOL_CALL: ... / ARGUMENTS: ...

        Args:
            output: Model output text

        Returns:
            List of parsed ToolCall objects
        """
        calls = []

        # Parse XML format
        calls.extend(self._parse_xml_calls(output))

        # Parse JSON format
        calls.extend(self._parse_json_calls(output))

        # Parse Markdown format
        calls.extend(self._parse_markdown_calls(output))

        return calls

    def _parse_xml_calls(self, output: str) -> list[ToolCall]:
        """Parse XML-formatted tool calls."""
        calls = []

        # Pattern for <tool_call>...</tool_call>
        pattern = r"<tool_call>\s*<name>([^<]+)</name>\s*<arguments>([^<]+)</arguments>\s*</tool_call>"
        matches = re.finditer(pattern, output, re.DOTALL | re.IGNORECASE)

        for match in matches:
            name = match.group(1).strip()
            args_str = match.group(2).strip()

            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError:
                arguments = {"raw": args_str}

            calls.append(ToolCall(
                name=name,
                arguments=arguments,
                raw_text=match.group(0),
            ))

        return calls

    def _parse_json_calls(self, output: str) -> list[ToolCall]:
        """Parse JSON-formatted tool calls."""
        calls = []

        # Pattern for {"tool": "...", "arguments": {...}}
        pattern = r'\{[^{}]*"tool"\s*:\s*"([^"]+)"[^{}]*"arguments"\s*:\s*(\{[^{}]*\})[^{}]*\}'
        matches = re.finditer(pattern, output, re.DOTALL)

        for match in matches:
            name = match.group(1)
            args_str = match.group(2)

            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError:
                arguments = {}

            calls.append(ToolCall(
                name=name,
                arguments=arguments,
                raw_text=match.group(0),
            ))

        return calls

    def _parse_markdown_calls(self, output: str) -> list[ToolCall]:
        """Parse Markdown-formatted tool calls."""
        calls = []

        # Pattern for TOOL_CALL: ... / ARGUMENTS: ...
        pattern = r"TOOL_CALL:\s*(\S+)\s*\nARGUMENTS:\s*(\{[^}]+\})"
        matches = re.finditer(pattern, output, re.MULTILINE)

        for match in matches:
            name = match.group(1).strip()
            args_str = match.group(2).strip()

            try:
                arguments = json.loads(args_str)
            except json.JSONDecodeError:
                arguments = {}

            calls.append(ToolCall(
                name=name,
                arguments=arguments,
                raw_text=match.group(0),
            ))

        return calls

    def inject_into_prompt(
        self,
        prompt: str,
        position: str = "start",  # start, end, marker
        marker: str = "{{TOOLS}}",
    ) -> str:
        """
        Inject tools section into a prompt.

        Args:
            prompt: Original prompt
            position: Where to inject (start, end, or marker)
            marker: Marker string to replace if position is 'marker'

        Returns:
            Prompt with tools section injected
        """
        tools_section = self.format_tools_section()

        if not tools_section:
            return prompt

        if position == "marker" and marker in prompt:
            return prompt.replace(marker, tools_section)
        elif position == "start":
            return f"{tools_section}\n\n{prompt}"
        else:  # end
            return f"{prompt}\n\n{tools_section}"

    def format_tool_result(
        self,
        call: ToolCall,
        result: Any,
        success: bool = True,
    ) -> str:
        """
        Format tool result for inclusion in conversation.

        Args:
            call: The tool call that was executed
            result: The result of the tool call
            success: Whether the call succeeded

        Returns:
            Formatted result string
        """
        if self.format_style == "xml":
            status = "success" if success else "error"
            return f"""<tool_result name="{call.name}" status="{status}">
{json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)}
</tool_result>"""
        elif self.format_style == "json":
            return json.dumps({
                "tool_result": {
                    "name": call.name,
                    "success": success,
                    "result": result,
                }
            }, indent=2)
        else:
            status = "✓" if success else "✗"
            return f"""**Tool Result [{status}]: {call.name}**
```
{json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)}
```"""
