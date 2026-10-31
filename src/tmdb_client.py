from typing import Any

import requests

BASE_URL = "https://api.themoviedb.org/3"
TIMEOUT = 10


class TMDBClient:
    """Cliente de la API de TMDB con una sesión HTTP autenticada"""

    def __init__(self, token: str) -> None:
        """Crea la sesión HTTP con el token como cabecera Authorization: Bearer"""
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def search_movies(self, title: str, year: str | None) -> list[dict[str, Any]]:
        """Busca películas en TMDB por título y, si se indica, por año.

        Solo devuelve la primera página de resultados (hasta 20), que suele
        bastar para encontrar la película buscada.

        Args:
            title: Título que se busca.
            year: Año de estreno, o None para buscar sin filtrar por año.

        Returns:
            Lista de resultados de TMDB, cada uno como diccionario con
            campos como id, title, original_title, release_date y
            vote_count. Vacía si no hay resultados.

        Raises:
            requests.HTTPError: Si TMDB responde con un código de error,
                por ejemplo 401 si el token no es válido.
            requests.RequestException: Si falla la conexión o se supera
                el tiempo de espera de TIMEOUT segundos.
        """
        response = self.session.get(
            f"{BASE_URL}/search/movie",
            params={"query": title, "primary_release_year": year},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        results: list[dict[str, Any]] = response.json()["results"]
        return results
