from typing import Any

import requests

BASE_URL = "https://api.themoviedb.org/3"
TIMEOUT = 10


class TMDBClient:
    """Cliente de la API de TMDB: guarda una sesión HTTP con la cabecera de autenticación"""

    def __init__(self, token: str) -> None:
        """Crea la sesión HTTP con el token como cabecera Authorization: Bearer"""
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def search_movies(self, title: str, year: str | None) -> list[dict[str, Any]]:
        """Busca películas por título (y año, si se indica) en TMDB y devuelve la lista de resultados"""
        response = self.session.get(
            f"{BASE_URL}/search/movie",
            params={"query": title, "primary_release_year": year},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        results: list[dict[str, Any]] = response.json()["results"]
        return results
