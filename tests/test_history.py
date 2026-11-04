from erp_asistan.history import History


def test_untouched_conversation_is_not_listed(tmp_path):
    assert History(tmp_path).list() == []


def test_first_user_message_becomes_title(tmp_path):
    h = History(tmp_path)

    h.add({"type": "user", "text": "Kritik stok?", "voice": False})
    h.add({"type": "turn", "reply": "Yok."})

    [item] = h.list()
    assert item["title"] == "Kritik stok?"
    assert item["id"] == h.current
    assert [e["type"] for e in h.get(item["id"])["events"]] == ["user", "turn"]


def test_start_opens_new_conversation_newest_first(tmp_path):
    h = History(tmp_path)
    h.add({"type": "user", "text": "ilk"})

    h.start()
    h.add({"type": "user", "text": "ikinci"})

    assert [i["title"] for i in h.list()] == ["ikinci", "ilk"]


def test_survives_restart(tmp_path):
    History(tmp_path).add({"type": "user", "text": "ilk"})

    h = History(tmp_path)

    assert [i["title"] for i in h.list()] == ["ilk"]
    assert h.get(h.current) is None


def test_unknown_or_malformed_id_returns_none(tmp_path):
    h = History(tmp_path)

    assert h.get("20990101-000000-000000") is None
    assert h.get("../.env") is None
