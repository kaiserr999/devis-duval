"""Tests de la documentation Swagger (Flasgger)."""


def test_apidocs_repond_200(client):
    reponse = client.get("/apidocs/")
    assert reponse.status_code == 200


def test_spec_documente_toutes_les_routes_api(app, client):
    spec = client.get("/apispec.json").get_json()

    attendues = set()
    for regle in app.url_map.iter_rules():
        if regle.rule.startswith("/api/"):
            chemin = regle.rule.replace("<int:", "{").replace(">", "}")
            for methode in regle.methods - {"HEAD", "OPTIONS"}:
                attendues.add((methode.lower(), chemin))
    documentees = {(methode, chemin)
                   for chemin, operations in spec["paths"].items()
                   for methode, operation in operations.items()
                   if operation.get("responses")}

    assert attendues
    assert attendues == documentees
