"""Task 5.2: chat sessions, saved messages, and the last turns the chat remembers."""

from sqlalchemy.orm import Session

from app.chat.memory import add_message, last_turns
from app.db.schema import ChatSession
from tests.fakes import api, login_as


def test_users_only_see_their_own_chats(db_session: Session) -> None:
    alice, bob = login_as(db_session, "alice"), login_as(db_session, "bob")
    first = api.post("/chat/sessions", json={"title": "payments"}, headers=alice).json()
    second = api.post("/chat/sessions", json={}, headers=alice).json()
    bobs = api.post("/chat/sessions", json={"title": "mine"}, headers=bob)
    assert bobs.status_code == 201 and first["title"] == "payments" and second["title"] is None

    listed = api.get("/chat/sessions", headers=alice).json()
    assert [c["id"] for c in listed] == [second["id"], first["id"]]  # most recently used first

    chat = db_session.get(ChatSession, first["id"])
    add_message(db_session, chat, "user", "who built the payment service?")
    db_session.commit()
    listed = api.get("/chat/sessions", headers=alice).json()
    assert [c["id"] for c in listed] == [first["id"], second["id"]]  # a new message moves it up

    assert [c["title"] for c in api.get("/chat/sessions", headers=bob).json()] == ["mine"]
    for chat_id in (bobs.json()["id"], 999):  # someone else's chat looks like a missing one
        response = api.get(f"/chat/sessions/{chat_id}/messages", headers=alice)
        assert response.status_code == 404 and response.json() == {"detail": "Chat not found"}
    assert api.post("/chat/sessions", json={"title": "x" * 301}, headers=alice).status_code == 422


def test_every_message_is_saved_in_order(db_session: Session) -> None:
    alice = login_as(db_session, "alice")
    chat_id = api.post("/chat/sessions", json={}, headers=alice).json()["id"]
    chat = db_session.get(ChatSession, chat_id)
    add_message(db_session, chat, "user", "hi")
    add_message(db_session, chat, "assistant", "Hi! Ask me about your team's work.")
    db_session.commit()  # same transaction, same created_at: the order comes from the ids

    listed = api.get(f"/chat/sessions/{chat_id}/messages", headers=alice).json()
    assert [(m["role"], m["content"]) for m in listed] == [
        ("user", "hi"),
        ("assistant", "Hi! Ask me about your team's work."),
    ]
    assert listed[0]["sources"] == [] and listed[0]["confidence"] is None


def test_the_11th_oldest_turn_is_not_loaded(db_session: Session) -> None:
    alice = login_as(db_session, "alice")
    chat, other = (
        db_session.get(ChatSession, api.post("/chat/sessions", json={}, headers=alice).json()["id"])
        for _ in range(2)
    )
    assert last_turns(db_session, chat.id) == []
    for n in range(1, 12):
        add_message(db_session, chat, "user", f"question {n}")
        if n != 7:  # a turn whose reply never came is still a turn
            add_message(db_session, chat, "assistant", f"answer {n}")
    add_message(db_session, other, "user", "a question in another chat")  # newest of all
    db_session.commit()

    remembered = [m.content for m in last_turns(db_session, chat.id)]  # CHAT_MEMORY_TURNS = 10
    assert remembered[0] == "question 2" and remembered[-1] == "answer 11"
    assert "question 1" not in remembered and "answer 1" not in remembered
    assert len(remembered) == 19 and "a question in another chat" not in remembered
    assert [m.content for m in last_turns(db_session, chat.id, turns=2)] == [
        "question 10",
        "answer 10",
        "question 11",
        "answer 11",
    ]
