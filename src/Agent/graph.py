from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agent.nodes.approval import Approval_Agent, route_after_approval
from src.agent.nodes.direct import direct
from src.agent.nodes.executor import Executor_agent
from src.agent.nodes.memory import memory
from src.agent.nodes.planner import Planner_Agent
from src.agent.nodes.router import router, decide
from src.agent.state import GmailState
from src.agent.tools import tools_list


async def agent_graph(checkpointer, state_schema=GmailState):
    g = StateGraph(state_schema)

    g.add_node("router", router)
    g.add_node("planner", Planner_Agent)
    g.add_node("ex", Executor_agent)
    g.add_node("tool", ToolNode(tools_list))
    g.add_node("memory", memory)
    g.add_node("direct", direct)
    g.add_node("approval_gate", Approval_Agent)

    g.add_edge(START, "memory")
    g.add_edge("memory", "router")
    g.add_conditional_edges(
        "router",
        decide,
        {
            "direct": "direct",
            "planner": "planner",
        },
    )
    g.add_edge("planner", "ex")
    g.add_conditional_edges(
        "ex",
        tools_condition,
        {"tools": "approval_gate", "__end__": END},
    )
    g.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "ex": "ex",
            "tool": "tool",
        },
    )
    g.add_edge("tool", "ex")
    g.add_edge("direct", END)

    return g.compile(checkpointer=checkpointer)
