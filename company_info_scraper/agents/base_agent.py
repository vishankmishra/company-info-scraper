"""
Base Agent class for Google ADK compatibility (PH5-S2)

This module provides a base class that:
1. Works standalone as a regular Python class
2. Can be wrapped as an ADK-compatible tool/agent
3. Provides async-first execution model
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
import logging
import asyncio
import functools

# ADK imports - graceful fallback if not installed
try:
    from google.adk import Agent
    from google.adk.tools import FunctionTool
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    Agent = object  # Fallback for type hints
    FunctionTool = None


@dataclass
class AgentToolSpec:
    """Specification for exposing an agent method as an ADK tool."""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all agents in the system.
    
    Provides:
    - Standalone execution via execute() and execute_async()
    - ADK compatibility via get_adk_tools() and as_adk_agent()
    - Consistent logging and validation patterns
    
    PH5-S2: Updated for Google ADK integration.
    """
    
    # Class-level registry of agent instances for ADK orchestration
    _registry: Dict[str, 'BaseAgent'] = {}
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"agent.{name}")
        self.logger.info(f"Initialized {self.name} agent")
        
        # Register this agent instance
        BaseAgent._registry[name] = self
        
        # ADK tool specifications (subclasses can add more)
        self._tool_specs: List[AgentToolSpec] = []
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main task (synchronous).
        
        Args:
            input_data: Input data for the agent
            
        Returns:
            Output data from the agent
        """
        pass
    
    async def execute_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main task (asynchronous).
        
        Default implementation runs execute() in a thread pool.
        Subclasses should override for true async implementation.
        
        Args:
            input_data: Input data for the agent
            
        Returns:
            Output data from the agent
        """
        return await asyncio.to_thread(self.execute, input_data)
    
    def validate_input(self, input_data: Dict[str, Any], required_fields: list) -> bool:
        """Validate that required fields are present in input."""
        missing = [field for field in required_fields if field not in input_data]
        if missing:
            self.logger.error(f"Missing required fields: {missing}")
            return False
        return True
    
    def log_result(self, result: Dict[str, Any], success: bool = True):
        """Log agent execution result."""
        if success:
            self.logger.info(f"{self.name} completed successfully")
        else:
            self.logger.error(f"{self.name} failed")
        self.logger.debug(f"Result: {result}")
    
    # =========================================================================
    # ADK Integration Methods (PH5-S2)
    # =========================================================================
    
    def register_tool(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Register a method as an ADK tool.
        
        Args:
            name: Tool name (used in ADK)
            description: Tool description for LLM
            func: The function to expose
            parameters: JSON schema for parameters
        """
        spec = AgentToolSpec(
            name=name,
            description=description,
            func=func,
            parameters=parameters or {}
        )
        self._tool_specs.append(spec)
        self.logger.debug(f"Registered tool: {name}")
    
    def get_tool_specs(self) -> List[AgentToolSpec]:
        """Get all registered tool specifications."""
        return self._tool_specs
    
    def get_adk_tools(self) -> List[Any]:
        """
        Get ADK FunctionTool wrappers for this agent's methods.
        
        Returns:
            List of ADK FunctionTool objects (or empty if ADK not available)
        """
        if not ADK_AVAILABLE or FunctionTool is None:
            self.logger.warning(
                "Google ADK not installed. Install with: pip install google-adk"
            )
            return []
        
        tools = []
        
        # Always expose the main execute method as a tool
        execute_tool = self._create_execute_tool()
        if execute_tool:
            tools.append(execute_tool)
        
        # Add any custom registered tools
        for spec in self._tool_specs:
            try:
                tool = FunctionTool(
                    name=spec.name,
                    description=spec.description,
                    func=spec.func
                )
                tools.append(tool)
            except Exception as e:
                self.logger.error(f"Failed to create tool {spec.name}: {e}")
        
        return tools
    
    def _create_execute_tool(self) -> Optional[Any]:
        """Create an ADK FunctionTool for the execute method."""
        if not ADK_AVAILABLE or FunctionTool is None:
            return None
        
        # Create a wrapper function with proper signature for ADK
        @functools.wraps(self.execute)
        def execute_wrapper(**kwargs) -> Dict[str, Any]:
            """Execute the agent with the provided input."""
            return self.execute(kwargs)
        
        # Set proper docstring
        execute_wrapper.__doc__ = self._get_execute_description()
        
        try:
            return FunctionTool(
                name=f"{self.name.lower()}_execute",
                description=self._get_execute_description(),
                func=execute_wrapper
            )
        except Exception as e:
            self.logger.error(f"Failed to create execute tool: {e}")
            return None
    
    def _get_execute_description(self) -> str:
        """Get description for the execute tool. Override in subclasses."""
        return f"Execute the {self.name} agent with the provided input data."
    
    def as_adk_agent(self, model: str = "gemini-2.0-flash") -> Optional[Any]:
        """
        Wrap this agent as an ADK LlmAgent.
        
        Args:
            model: The LLM model to use for agent reasoning
            
        Returns:
            ADK Agent instance or None if ADK not available
        """
        if not ADK_AVAILABLE:
            self.logger.warning(
                "Google ADK not installed. Cannot create ADK agent wrapper."
            )
            return None
        
        try:
            from google.adk import LlmAgent
            
            tools = self.get_adk_tools()
            
            agent = LlmAgent(
                name=self.name,
                model=model,
                instruction=self._get_agent_instruction(),
                tools=tools
            )
            
            self.logger.info(f"Created ADK LlmAgent wrapper for {self.name}")
            return agent
            
        except ImportError:
            self.logger.error("google.adk.LlmAgent not found")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create ADK agent: {e}")
            return None
    
    def _get_agent_instruction(self) -> str:
        """Get instruction for ADK LlmAgent. Override in subclasses."""
        return f"""You are the {self.name} agent.
Your role is to execute tasks using the available tools.
Always use the appropriate tool for the requested task.
Return structured results in JSON format."""
    
    # =========================================================================
    # Registry Methods (for ADK orchestration)
    # =========================================================================
    
    @classmethod
    def get_agent(cls, name: str) -> Optional['BaseAgent']:
        """Get a registered agent by name."""
        return cls._registry.get(name)
    
    @classmethod
    def get_all_agents(cls) -> Dict[str, 'BaseAgent']:
        """Get all registered agents."""
        return cls._registry.copy()
    
    @classmethod
    def clear_registry(cls):
        """Clear the agent registry."""
        cls._registry.clear()


def adk_tool(name: str, description: str):
    """
    Decorator to mark a method as an ADK tool.
    
    Usage:
        @adk_tool("scrape_domain", "Scrape a website domain")
        def scrape(self, domain: str) -> Dict[str, Any]:
            ...
    """
    def decorator(func):
        func._adk_tool_name = name
        func._adk_tool_description = description
        return func
    return decorator


# Utility function to check ADK availability
def is_adk_available() -> bool:
    """Check if Google ADK is installed and available."""
    return ADK_AVAILABLE
