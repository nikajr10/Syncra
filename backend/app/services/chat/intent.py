"""Intent router (Task 5.5): is a chat message small talk, a question or an action? (SetFit)

The classifier is trained on config/intent_router.yaml (`make train-intent-router`). Small talk
("hi", "thanks") gets an instant canned reply: no search and no LLM. A question goes on to search
(Phase 6) and an action to an approval card (Phase 8).
"""

from __future__ import annotations

import re

from app.ml import gateway

SMALL_TALK, QUESTION, ACTION = "small_talk", "question", "action"  # labels in intent_router.yaml

HELP = (
    "I'm Syncra, your team's memory. Ask me about your GitHub, Jira and Slack: who built "
    "something, what was decided and why, or what a ticket or pull request says. I answer from "
    "what I find there and show my sources."
)
GOT_IT = "Got it. Ask me anything about your team's work."
REPLIES = (  # small talk: the first pattern found in the message picks the reply, else GOT_IT
    (
        re.compile(r"\b(thanks?|thank (you|u)|thx|ty|tysm|cheers|appreciated?)\b|🙏", re.I),
        "You're welcome! Ask me anything else about your team's work.",
    ),
    (
        re.compile(r"\b(bye|goodbye|see (you|ya)|good night|talk later|gotta go)\b", re.I),
        "Bye! Ask me again any time.",
    ),
    (
        re.compile(r"\b(help|who are you|what are you|what (can|do) you|how (does|can) )", re.I),
        HELP,
    ),
    (
        re.compile(
            r"\b(hi|hello|hey|hiya|howdy|yo|sup|morning|afternoon|evening|greetings|how are you"
            r"|how's it going)\b|👋",
            re.I,
        ),
        "Hi! I'm Syncra. Ask me about your team's GitHub, Jira and Slack: who built what, what "
        "was decided and why.",
    ),
)


def route(message: str) -> str:
    """The path a message takes: SMALL_TALK, QUESTION or ACTION."""
    return gateway.classify("intent_router", [message])[0]


def small_talk_reply(message: str) -> str:
    """An instant canned reply to small talk."""
    return next((reply for pattern, reply in REPLIES if pattern.search(message)), GOT_IT)
