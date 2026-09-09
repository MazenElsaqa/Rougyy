from ai_database_agent.memory.conversation import Conversation, ConversationTurn


def test_new_conversation_is_empty():
    conversation = Conversation()

    assert conversation.is_empty()
    assert conversation.recent() == []
    assert conversation.context_text() == ""


def test_add_turn_records_question_sql_and_answer():
    conversation = Conversation()

    conversation.add_turn(
        question="Which singers are from France?",
        sql="SELECT name FROM singer WHERE country = 'France'",
        answer="Found 3 singers from France.",
    )

    assert not conversation.is_empty()
    assert len(conversation.turns) == 1
    turn = conversation.turns[0]
    assert isinstance(turn, ConversationTurn)
    assert turn.question == "Which singers are from France?"
    assert turn.sql == "SELECT name FROM singer WHERE country = 'France'"
    assert turn.answer == "Found 3 singers from France."


def test_context_text_joins_questions_in_order():
    conversation = Conversation()
    conversation.add_turn("Which singers are from France?", "SQL 1", "answer 1")
    conversation.add_turn("What about from Canada?", "SQL 2", "answer 2")

    assert conversation.context_text() == "Which singers are from France? What about from Canada?"


def test_recent_returns_turns_in_order():
    conversation = Conversation()
    conversation.add_turn("Q1", "SQL 1", "A1")
    conversation.add_turn("Q2", "SQL 2", "A2")

    recent = conversation.recent()

    assert [t.question for t in recent] == ["Q1", "Q2"]


def test_conversation_window_drops_oldest_turns_beyond_max_turns():
    conversation = Conversation(max_turns=2)
    conversation.add_turn("Q1", "SQL 1", "A1")
    conversation.add_turn("Q2", "SQL 2", "A2")
    conversation.add_turn("Q3", "SQL 3", "A3")

    assert [t.question for t in conversation.turns] == ["Q2", "Q3"]


def test_recent_returns_a_copy_not_a_live_reference():
    conversation = Conversation()
    conversation.add_turn("Q1", "SQL 1", "A1")

    snapshot = conversation.recent()
    conversation.add_turn("Q2", "SQL 2", "A2")

    assert len(snapshot) == 1
    assert len(conversation.turns) == 2
