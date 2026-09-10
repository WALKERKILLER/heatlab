from heatlab.web.app import TOPIC_PAGES, create_app


def test_each_topic_has_a_standalone_web_page() -> None:
    client = create_app().test_client()
    for topic_id in TOPIC_PAGES:
        response = client.get(f"/topic/{topic_id}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert f'data-default-topic="{topic_id}"' in html
        assert 'data-standalone="true"' in html


def test_web_app_can_start_locked_to_one_topic() -> None:
    client = create_app("brownian").test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-default-topic="brownian"' in html
    assert 'data-standalone="true"' in html
    assert client.get("/topic/maxwell").status_code == 404


def test_unknown_topic_page_is_not_available() -> None:
    assert create_app().test_client().get("/topic/not-a-topic").status_code == 404
