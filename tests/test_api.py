def create_project(client) -> str:
    resp = client.post(
        "/create",
        data={
            "title": "爷爷的一生",
            "narrator_name": "张桂芬",
            "interviewer_name": "阿哲",
            "dedication": "献给我们家最会讲故事的人",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return resp.headers["location"].rstrip("/").split("/")[-1]


def test_healthz(client):
    data = client.get("/healthz").json()
    assert data["ok"] is True
    assert data["ai_enabled"] is False


def test_home_page_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "往事榨汁机" in resp.text


def test_create_project_redirects_to_editor(client):
    token = create_project(client)
    resp = client.get(f"/project/{token}")
    assert resp.status_code == 200
    assert "爷爷的一生" in resp.text
    assert "张桂芬" in resp.text


def test_missing_project_returns_404(client):
    assert client.get("/project/not-a-real-token").status_code == 404


def test_next_question_returns_first_ice_question(client):
    token = create_project(client)
    data = client.get(f"/api/projects/{token}/question?topic=childhood").json()
    assert data["finished"] is False
    assert data["topic"] == "childhood"
    assert data["question"]["id"] == "childhood-1"


def test_create_story_offline_polish_and_book(client):
    token = create_project(client)

    resp = client.post(
        f"/api/projects/{token}/stories",
        data={
            "topic": "childhood",
            "question": "您小时候住的那个地方，是什么样子的？",
            "text": "那时候我们住在河边，门口有棵老槐树，夏天就在树底下乘凉，蚊子多得很，俺妈就拿蒲扇给我们扇",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    story = payload["story"]
    assert story["polished_text"]
    assert payload["polish_ok"] is False
    assert story["provider"] == "offline"

    book = client.get(f"/book/{token}")
    assert book.status_code == 200
    assert "老槐树" in book.text
    assert "本书由 阿哲 献给 张桂芬" in book.text


def test_answered_question_is_not_offered_again(client):
    token = create_project(client)
    first = client.get(f"/api/projects/{token}/question?topic=childhood").json()
    client.post(
        f"/api/projects/{token}/stories",
        data={"topic": "childhood", "question": first["question"]["text"], "text": "我小时候住在山脚下"},
    )
    second = client.get(f"/api/projects/{token}/question?topic=childhood").json()
    assert second["question"]["id"] == "childhood-2"


def test_edit_story_text(client):
    token = create_project(client)
    resp = client.post(
        f"/api/projects/{token}/stories",
        data={"topic": "youth", "text": "第一次离家去县城上学，是走路去的"},
    )
    story_id = resp.json()["story"]["id"]

    patched = client.patch(f"/api/stories/{story_id}", data={"polished_text": "我改过的版本"})
    assert patched.status_code == 200
    assert patched.json()["story"]["polished_text"] == "我改过的版本"


def test_followup_falls_back_to_local_template_without_api_key(client):
    token = create_project(client)
    resp = client.post(f"/api/projects/{token}/stories", data={"topic": "work", "text": "我第一份工作是在厂里"})
    story_id = resp.json()["story"]["id"]
    follow = client.post(f"/api/stories/{story_id}/followup")
    assert follow.status_code == 200
    data = follow.json()
    assert data["question"]
    assert data["ai_generated"] is False
    assert data["provider"] == "offline"


def test_delete_story(client):
    token = create_project(client)
    resp = client.post(f"/api/projects/{token}/stories", data={"topic": "family", "text": "我们是经人介绍认识的"})
    story_id = resp.json()["story"]["id"]
    assert client.delete(f"/api/stories/{story_id}").status_code == 200
    assert client.get(f"/api/projects/{token}/question?topic=family").json()["question"]["id"] == "family-1"


def test_unknown_topic_rejected(client):
    token = create_project(client)
    resp = client.post(f"/api/projects/{token}/stories", data={"topic": "nope", "text": "随便说说"})
    assert resp.status_code == 400