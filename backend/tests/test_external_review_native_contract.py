"""Native provider shape: optional place info, per-page provenance and isolation."""

import httpx
import pytest

from test_external_review_import_api import (
    BUSINESS, FOREIGN, api, counts, env, post, record, synthetic_only,
)


def native_page(*rows, token=None, business=BUSINESS, place=True):
    body = {
        "search_metadata": {"status": "Success", "google_maps_reviews_url":
                            f"https://www.google.com/maps/place/data=!4m7!3m6!1s{business}!5m2!4m1!1i2!9m1!1b1?hl=es"},
        "search_parameters": {"engine": "google_maps_reviews", "data_id": business},
        "reviews": list(rows),
    }
    if place:
        body["place_info"] = {"title": "Negocio sintético", "reviews": 2, "rating": 4.3}
    if token:
        body["serpapi_pagination"] = {"next_page_token": token}
    return body


def test_native_first_page_without_place_data_id_and_pagination_without_place_info(env, api):
    env.current_service = env.service(max_pages=2)
    env.handler = lambda _: httpx.Response(200, json=(
        native_page(record("one"), token="synthetic-next") if len(env.calls) == 1 else
        native_page(record("two"), place=False)))
    response = post(api)
    assert response.status_code == 200
    assert response.json()["inserted"] == 2
    assert counts(env) == (2, 2)
    assert env.calls[1][1] == "synthetic-next"


@pytest.mark.parametrize("tamper", [
    "foreign_parameters", "foreign_url", "foreign_page", "missing_parameters", "missing_url",
    "untrusted_host", "userinfo", "wrong_engine", "contradictory_place", "query_only_identity",
])
def test_every_page_rejects_missing_or_conflicting_native_evidence(env, api, tamper):
    env.current_service = env.service(max_pages=2)
    second = native_page(record("two"), place=False)
    if tamper == "foreign_parameters":
        second["search_parameters"]["data_id"] = FOREIGN
    elif tamper == "foreign_url":
        second["search_metadata"]["google_maps_reviews_url"] = native_page(business=FOREIGN)["search_metadata"]["google_maps_reviews_url"]
    elif tamper == "foreign_page":
        second = native_page(record("two"), business=FOREIGN)
    elif tamper == "missing_parameters":
        second.pop("search_parameters")
    elif tamper == "missing_url":
        second["search_metadata"].pop("google_maps_reviews_url")
    elif tamper == "untrusted_host":
        second["search_metadata"]["google_maps_reviews_url"] = f"https://www.google.com.invalid/maps/place/data=!1s{BUSINESS}!1b1"
    elif tamper == "userinfo":
        second["search_metadata"]["google_maps_reviews_url"] = f"https://private@www.google.com/maps/place/data=!1s{BUSINESS}!1b1"
    elif tamper == "wrong_engine":
        second["search_parameters"]["engine"] = "google"
    elif tamper == "contradictory_place":
        second["place_info"] = {"data_id": FOREIGN}
    elif tamper == "query_only_identity":
        second["search_metadata"]["google_maps_reviews_url"] = f"https://www.google.com/maps/place/other?data=!1s{BUSINESS}"
    env.handler = lambda _: httpx.Response(200, json=(
        native_page(record("one"), token="synthetic-next") if len(env.calls) == 1 else second))
    response = post(api)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "place_unverified"
    assert response.json()["detail"]["committed_count"] == 0
    assert counts(env) == (0, 0)
