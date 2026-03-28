"""
LangGraph/LangChain-based AI preparation for dermatology consultations.

FIX 4: In the internal-consultation branch:
- Do NOT purge system prompt
- Simply do: response = llm.invoke(messages) and return
- Remove all clinical_override and purged_history logic
"""

import os

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


def _get_llm(model: str = 'gpt-4.1', temperature: float = 0.3):
    """Initialize and return the LangChain LLM."""
    if not LANGCHAIN_AVAILABLE:
        raise ImportError(
            'langchain-openai is required. '
            'Add langchain-openai to requirements.txt and re-deploy.'
        )
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=os.environ.get('OPENAI_API_KEY'),
    )


def _extract_content(response) -> str:
    """Extract text content from an LLM response object."""
    if response is None:
        return ''
    content = getattr(response, 'content', response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get('type') == 'text':
                text = part.get('text', '').strip()
                if text:
                    return text
    return ''


def _build_messages(system_prompt: str, conversation: list, user_message: str) -> list:
    """Build a LangChain message list from system prompt, conversation history, and new user message."""
    messages = [SystemMessage(content=system_prompt)]
    for msg in conversation:
        role = (msg.get('role') or '').lower()
        content = msg.get('content', '')
        if role in ('user', 'patient'):
            messages.append(HumanMessage(content=content))
        elif role in ('ai', 'assistant'):
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_message))
    return messages


def run_education_graph(system_prompt: str, conversation: list, user_message: str) -> str:
    """
    Run AI for general_education mode.
    Returns AI response string.
    """
    llm = _get_llm(model='gpt-4.1', temperature=0.4)
    messages = _build_messages(system_prompt, conversation, user_message)
    response = llm.invoke(messages)
    return _extract_content(response)


def run_internal_consultation(system_prompt: str, conversation: list, user_message: str) -> str:
    """
    Run AI for doctor internal consultation (draft generation, mode 4/5).

    FIX 4:
    - Do NOT purge system prompt
    - Simply invoke llm.invoke(messages) and return
    - No clinical_override or purged_history logic
    """
    llm = _get_llm(model='gpt-4.1', temperature=0.2)
    messages = _build_messages(system_prompt, conversation, user_message)

    # FIX 4: Simply invoke and return — no purge, no clinical_override
    response = llm.invoke(messages)
    return _extract_content(response)
