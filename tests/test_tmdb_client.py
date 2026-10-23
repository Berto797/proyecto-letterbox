from typing import Any

import pytest
import requests

from tmdb_client import TMDBClient


class FakeResponse:
    """Respuesta falsa de requests: devuelve un JSON preparado o lanza un error"""

    def __init__(self, payload: dict[str, Any], error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def json(self) -> dict[str, Any]:
        return self.payload

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error


class FakeSession:
    """Sesión falsa que guarda cada llamada a get y devuelve una respuesta preparada"""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.response


@pytest.fixture
def session() -> FakeSession:
    return FakeSession(FakeResponse({"results": []}))


@pytest.fixture
def client(session: FakeSession, monkeypatch: pytest.MonkeyPatch) -> TMDBClient:
    client = TMDBClient("fake-token")
    monkeypatch.setattr(client, "session", session)
    return client


def test_tmdb_client_sets_auth_header() -> None:
    client = TMDBClient("fake-token")

    assert client.session.headers["Authorization"] == "Bearer fake-token"


@pytest.mark.parametrize(
    "year, expected_params",
    [
        pytest.param(
            "2021",
            {"query": "Oslo", "primary_release_year": "2021"},
            id="with_year",
        ),
        pytest.param(
            None,
            {"query": "Oslo", "primary_release_year": None},
            id="without_year",
        ),
    ],
)
def test_search_movies_sends_request(
    year: str | None,
    expected_params: dict[str, Any],
    client: TMDBClient,
    session: FakeSession,
) -> None:
    client.search_movies("Oslo", year)

    assert session.calls == [
        {
            "url": "https://api.themoviedb.org/3/search/movie",
            "params": expected_params,
            "timeout": 10,
        }
    ]


def test_search_movies_returns_results(
    client: TMDBClient, session: FakeSession
) -> None:
    session.response = FakeResponse({"results": [{"id": 1, "title": "Oslo"}]})

    result = client.search_movies("Oslo", "2021")

    assert result == [{"id": 1, "title": "Oslo"}]


def test_search_movies_raises_on_http_error(
    client: TMDBClient, session: FakeSession
) -> None:
    session.response = FakeResponse({}, error=requests.HTTPError("401"))

    with pytest.raises(requests.HTTPError):
        client.search_movies("Oslo", "2021")
