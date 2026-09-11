"""
Intent gate: is this message a database question or plain chat?

`AgentPipeline.ask()` used to treat *every* input as a database
question -- a greeting like "how are you today" would get schema
linked, fed to the SQL generator, retried 3 times, and finally
answered with "no matching results". This module adds a cheap gate
in front:

1. Heuristic fast-path (no LLM call): obvious greetings/thanks/
   goodbyes in English or Arabic short-circuit to CHAT instantly.
2. LLM classifier (one short call on the small chat model): anything
   ambiguous is classified as CHAT or DATA_QUERY, failing open to
   DATA_QUERY so a real question is never refused.

CHAT messages never touch schema linking or SQL generation at all.
"""
from __future__ import annotations

import re
import unicodedata

from ai_database_agent.llm.client import get_llm_client, llm_answer_model_name
from ai_database_agent.llm.prompts import INTENT_CLASSIFICATION_SYSTEM_PROMPT
from ai_database_agent.memory.conversation import ConversationTurn
from ai_database_agent.observability.tracing import get_tracer

_tracer = get_tracer(__name__)

CHAT = "CHAT"
DATA_QUERY = "DATA_QUERY"

# Obvious small-talk, matched against the whole normalized message.
# Deliberately conservative: anything with data flavor ("hi, how many
# singers...") won't match and falls through to the LLM classifier.
_GREETINGS = frozenset(
    {
        # English greetings / small talk
        "hi", "hey", "hello", "yo", "hiya", "hi there", "hello there",
        "hey there", "good morning", "good afternoon", "good evening",
        "good night",         "how are you", "how are u", "how r u",
        "how is it going", "what is up", "whats up",
        "how do you do", "nice to meet you",
        "who are you", "what are you", "what can you do", "what do you do",
        "help", "help me", "thanks", "thank you", "thx",
        "thanks a lot", "thank you very much", "bye", "goodbye", "see you",
        "see you later", "how are you today", "how are you doing",
        # Arabic greetings / small talk
        "مرحبا", "اهلا", "أهلا", "السلام عليكم", "عليكم السلام",
        "ازيك", "ازيكم", "عامل ايه", "عامله ايه", "عاملين ايه",
        "اخبارك", "أخبارك", "صباح الخير", "مساء الخير", "تصبح على خير",
        "مع السلامه", "مع السلامة", "انت مين", "إنت مين", "بتعمل ايه",
        "بتعملي ايه", "ممكن تساعدني", "ساعدني", "شكرا", "شكراً",
        "شكرا جزيلا", "متشكر", "متشكره", "تمام", "اهلا بيك",
    }
)

_PUNCT_RE = re.compile(r"[!?.,،؛:؛؟\-_~*\"'()\[\]«»]+")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip().lower())
    text = _PUNCT_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def looks_like_small_talk(question: str) -> bool:
    """Heuristic fast-path: True only for short messages that fully
    match a known greeting/thanks pattern. Never touches the LLM."""
    normalized = _normalize(question)
    return bool(normalized) and len(normalized) <= 60 and normalized in _GREETINGS


class IntentClassifier:
    """CHAT vs DATA_QUERY, heuristic first, one LLM call on ambiguity."""

    def __init__(self, client=None, model: str | None = None):
        self._client = client
        self._model = model

    def _llm(self):
        return self._client or get_llm_client()

    def _model_name(self) -> str:
        return self._model or llm_answer_model_name()

    def classify(
        self,
        question: str,
        table_names: list[str] | None = None,
        conversation_turns: list[ConversationTurn] | None = None,
    ) -> str:
        with _tracer.start_as_current_span("llm.classify_intent") as span:
            span.set_attribute("intent.question_length", len(question))
            if looks_like_small_talk(question):
                span.set_attribute("intent.result", CHAT)
                span.set_attribute("intent.via", "heuristic")
                return CHAT

            tables_hint = ", ".join(table_names or [])
            context = ""
            if conversation_turns:
                last = conversation_turns[-1]
                context = f"Previous question: {last.question}\nPrevious answer: {last.answer}\n"

            response = self._llm().chat.completions.create(
                model=self._model_name(),
                temperature=0,
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFICATION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Database tables: {tables_hint}\n{context}"
                            f"User message: {question}\nIntent:"
                        ),
                    },
                ],
            )
            raw = (response.choices[0].message.content or "").strip().upper()
            # Fail open: anything unparseable is treated as a data
            # question, i.e. the pre-gate behavior. A greeting answered
            # as CHAT is nice; a data question answered as CHAT would
            # be a refusal, which is worse.
            intent = CHAT if raw.split()[0:1] == [CHAT] else DATA_QUERY
            span.set_attribute("intent.result", intent)
            span.set_attribute("intent.via", "llm")
            return intent
