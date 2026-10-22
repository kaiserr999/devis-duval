"""Tests de la vérification de SECRET_KEY au démarrage."""
import pytest

from app import create_app
from app.config import CLE_DEV, TestConfig


class SansCle(TestConfig):
    SECRET_KEY = None


class CleDev(TestConfig):
    SECRET_KEY = CLE_DEV


@pytest.mark.parametrize("config", [SansCle, CleDev])
def test_refuse_de_demarrer_sans_vraie_cle(config, monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(config)


def test_cle_de_dev_acceptee_en_debug(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "1")
    app = create_app(SansCle)
    assert app.config["SECRET_KEY"] == CLE_DEV


def test_vraie_cle_conservee():
    app = create_app(TestConfig)
    assert app.config["SECRET_KEY"] == "cle-de-test"


class DerriereProxy(TestConfig):
    DERRIERE_PROXY = True


@pytest.mark.parametrize("config, https_attendu", [(TestConfig, False),
                                                   (DerriereProxy, True)])
def test_https_du_proxy_seulement_si_demande(config, https_attendu):
    app = create_app(config)

    @app.get("/test-schema")
    def schema():
        from flask import request
        return request.scheme

    reponse = app.test_client().get(
        "/test-schema", headers={"X-Forwarded-Proto": "https"})
    assert reponse.get_data(as_text=True) == \
        ("https" if https_attendu else "http")
