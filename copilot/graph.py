"""Wire the investigation graph.

Flow: planner fans out (in parallel) to whichever specialist sources it chose;
the branches rejoin at ``gather``; then code-executor → critic → synthesizer run
sequentially. ``build_graph(deps)`` injects the LLM factory + AWS config, so the
same graph is used in production and in tests (with stubs).
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .deps import Deps
from .nodes.aws_investigator import make_aws_investigator
from .nodes.code_executor import make_code_executor
from .nodes.critic import make_critic
from .nodes.github_diff import make_github_node
from .nodes.planner import make_planner
from .nodes.rag import make_rag_node
from .nodes.synthesizer import make_synthesizer
from .state import State

_SOURCE_TO_NODE = {"aws": "aws", "github": "github", "rag": "rag"}


def _fan_out(state: State) -> list[str]:
    """Pick the specialist nodes the planner selected (dedup, fall back to rag)."""
    chosen = {_SOURCE_TO_NODE[t.source] for t in state.get("threads", []) if t.source in _SOURCE_TO_NODE}
    return sorted(chosen) or ["rag"]


def build_graph(deps: Deps):
    g = StateGraph(State)

    g.add_node("planner", make_planner(deps))
    g.add_node("aws", make_aws_investigator(deps))
    g.add_node("github", make_github_node(deps))
    g.add_node("rag", make_rag_node(deps))
    g.add_node("gather", lambda state: {})  # join point for the parallel branches
    g.add_node("code", make_code_executor(deps))
    g.add_node("critic", make_critic(deps))
    g.add_node("synthesizer", make_synthesizer(deps))

    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", _fan_out, ["aws", "github", "rag"])
    for node in ("aws", "github", "rag"):
        g.add_edge(node, "gather")
    g.add_edge("gather", "code")
    g.add_edge("code", "critic")
    g.add_edge("critic", "synthesizer")
    g.add_edge("synthesizer", END)

    return g.compile()
