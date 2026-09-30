from app.services.llm.attachments import normalize_attachment_meta


def test_agent_file_id_and_warnings_stay_with_the_message():
    meta = normalize_attachment_meta([{
        "name": "offer.pdf", "mime": "application/pdf", "size": 12, "id": "a" * 32,
        "warnings": ["No text on page 4.", "", 3], "data": "must never be stored",
    }])
    assert meta == [{"name": "offer.pdf", "mime": "application/pdf", "size": 12, "id": "a" * 32,
                     "warnings": ["No text on page 4."]}]


def test_foreign_ids_are_dropped_and_consensus_meta_is_unchanged():
    meta = normalize_attachment_meta([
        {"name": "a.txt", "mime": "text/plain", "size": 1, "id": "../../other"},
        {"name": "b.txt", "mime": "text/plain", "size": 2, "id": "A" * 32},
    ])
    assert meta == [{"name": "a.txt", "mime": "text/plain", "size": 1},
                    {"name": "b.txt", "mime": "text/plain", "size": 2}]
    assert normalize_attachment_meta([{"name": "c.txt", "mime": "text/plain", "size": 3}]) == [
        {"name": "c.txt", "mime": "text/plain", "size": 3}]
