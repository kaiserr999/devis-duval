"""Tests de la route /api/health."""


def test_health_repond_200(client):
    reponse = client.get("/api/health")
    assert reponse.status_code == 200
    assert reponse.get_json() == {"statut": "ok"}
