from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from src.Agent.Agent_functions import GmailAgentNodes
from src.Agent.Agent_States import GmailState


async def agent_graph(nodes: GmailAgentNodes, tools_list: list, checkpointer, state_schema=GmailState):
    g = StateGraph(state_schema)


    g.add_node("router",   nodes.router)
    g.add_node("planner",  nodes.Planner_Agent)
    g.add_node("ex",       nodes.Executor_agent)
    g.add_node("tool",     ToolNode(tools_list))
    g.add_node("memory",   nodes.memory)
    g.add_node("direct",   nodes.direct)
    g.add_node("val",   nodes.Validator_Agent)
    g.add_node("approval_gate", nodes.Approval_Agent)

    g.add_edge(START, "memory")
    g.add_edge("memory", "router")
    g.add_conditional_edges("router", nodes.decide, {
        "direct":  "direct",
        "planner": "planner",
    })
    g.add_edge("planner", "ex")
    g.add_conditional_edges("ex", tools_condition, {
        "tools": "approval_gate",
        "__end__": "val",
    })
    g.add_conditional_edges("approval_gate",nodes.route_after_approval, {
        "ex": "ex",
        "tool": "tool",
    })
    g.add_edge("tool", "ex")
    g.add_edge("val",END)
    g.add_edge("direct",  END)

    return g.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    pass