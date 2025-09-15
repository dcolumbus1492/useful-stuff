#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic-ai>=0.0.14",
#   "mcp>=1.0.0",
#   "httpx>=0.27.0",
# ]
# ///

"""
Ollama MCP Server - Run LLM inference via Pydantic AI direct calls

Default model: gpt-oss:20b (13GB GPT-like model optimized for general tasks)

This MCP server provides a single tool 'run_inference' that:
- Takes a system prompt (function definition)
- Takes an output type (JSON schema for structured output)
- Takes a user prompt (input to the system)
- Runs inference on Ollama models using Pydantic AI direct calls
"""

import asyncio
import json
import os
from typing import Any, Dict, Optional
from mcp.server import Server
from mcp.types import TextContent, Tool
from pydantic_ai.direct import model_request
from pydantic_ai.messages import ModelRequest, SystemPromptPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.models import ModelRequestParameters, OutputObjectDefinition, ModelSettings


async def run_inference(args: Dict[str, Any]) -> list[TextContent]:
    """
    Run inference on an Ollama model with structured output.

    Args:
        system_prompt: The system prompt defining the task/function
        output_type: JSON schema defining the expected output structure
        user_prompt: The user input to process
        model: Optional Ollama model name (default: llama3.2)
        ollama_base_url: Optional Ollama server URL (default: http://localhost:11434/v1)
    """
    try:
        # Extract parameters
        system_prompt = args["system_prompt"]
        output_schema = args["output_type"]
        user_prompt = args["user_prompt"]
        model_name = args.get("model", "gpt-oss:20b")
        base_url = args.get("ollama_base_url", "http://localhost:11434/v1")

        # Create Ollama model instance with fixed temperature
        ollama_model = OpenAIChatModel(
            model_name=model_name,
            provider=OllamaProvider(base_url=base_url),
            settings=ModelSettings(temperature=0.2)
        )

        # Prepare the message with system and user prompts
        messages = [
            ModelRequest(parts=[
                SystemPromptPart(system_prompt),
                UserPromptPart(user_prompt)
            ])
        ]

        # Check if structured output is requested
        if output_schema:
            # Create output object definition from the schema
            output_object = OutputObjectDefinition(
                name="structured_output",
                description="Structured output based on provided schema",
                json_schema=output_schema
            )

            # Configure request parameters for structured output
            # Try native mode first, fallback to prompted for broader compatibility
            params = ModelRequestParameters(
                output_mode='prompted',  # Using prompted mode for better Ollama compatibility
                output_object=output_object,
                allow_text_output=False
            )

            # Make the request with structured output
            response = await model_request(
                ollama_model,
                messages,
                model_request_parameters=params
            )
        else:
            # Make a simple text request without structured output
            response = await model_request(
                ollama_model,
                messages
            )

        # Extract the response content
        response_text = ""
        response_data = None

        for part in response.parts:
            if hasattr(part, 'content'):
                response_text = part.content
                # Try to parse as JSON if it looks like JSON
                if response_text.strip().startswith('{') or response_text.strip().startswith('['):
                    try:
                        response_data = json.loads(response_text)
                    except:
                        pass  # Keep as text if not valid JSON
            elif hasattr(part, 'data'):
                # For structured output
                response_data = part.data

        # Return the result
        if response_data:
            return [TextContent(type="text", text=json.dumps(response_data, indent=2))]
        else:
            return [TextContent(type="text", text=response_text)]

    except Exception as e:
        error_msg = f"Error running inference: {str(e)}\n\nMake sure:\n1. Ollama is running (ollama serve)\n2. The model '{model_name}' is pulled (ollama pull {model_name})\n3. The Ollama server is accessible at {base_url}"
        return [TextContent(type="text", text=error_msg)]


# Create the MCP server
server = Server(name="ollama-inference")

# Register the tool
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="run_inference",
            description="Run LLM inference with structured output using Ollama models",
            inputSchema={
                "type": "object",
                "properties": {
                    "system_prompt": {"type": "string", "description": "System prompt defining the task/function"},
                    "output_type": {"type": "object", "description": "JSON schema for structured output"},
                    "user_prompt": {"type": "string", "description": "User input to process"},
                    "model": {"type": "string", "description": "Ollama model name (default: gpt-oss:20b)"},
                    "ollama_base_url": {"type": "string", "description": "Ollama server URL (default: http://localhost:11434/v1)"}
                },
                "required": ["system_prompt", "user_prompt"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, args: dict) -> list[TextContent]:
    if name == "run_inference":
        return await run_inference(args)
    raise ValueError(f"Unknown tool: {name}")


# Example usage when run directly
async def main():
    """Example usage of the Ollama inference tool"""

    # Example 1: Simple text generation
    result = await run_inference({
        "system_prompt": "You are a helpful assistant that explains concepts clearly.",
        "output_type": None,
        "user_prompt": "What is machine learning in simple terms?"
    })
    print("Example 1 - Simple text:")
    print(result[0].text)
    print("\n" + "="*50 + "\n")

    # Example 2: Structured output
    person_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "occupation": {"type": "string"}
        },
        "required": ["name", "age", "occupation"]
    }

    result = await run_inference({
        "system_prompt": "Extract person information from the text and return it as structured data.",
        "output_type": person_schema,
        "user_prompt": "John Smith is a 32-year-old software engineer working at Tech Corp."
    })
    print("Example 2 - Structured output:")
    print(result[0].text)


if __name__ == "__main__":
    import sys

    # Check if running as MCP server
    if "--mcp" in sys.argv or "MCP" in os.environ.get("MCP_MODE", ""):
        # Run as MCP server
        import mcp.server.stdio
        asyncio.run(mcp.server.stdio.stdio_server(server))
    else:
        # Run examples
        asyncio.run(main())