"""Cliente de la API de TMDB (búsqueda de películas)."""

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

BASE_URL = "https://api.themoviedb.org/3"
TIMEOUT = 10
MAX_RETRIES = 3
BACKOFF_FACTOR = 1
RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class TMDBClient:
    """Cliente de la API de TMDB con una sesión HTTP autenticada."""

    def __init__(self, token: str) -> None:
        """Crea la sesión HTTP autenticada y con reintentos ante errores temporales."""
        retry = Retry(
            total=MAX_RETRIES,
            status_forcelist=RETRY_STATUS_CODES,
            backoff_factor=BACKOFF_FACTOR,
            raise_on_status=False,
        )
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def search_movies(self, title: str, year: str | None) -> list[dict[str, Any]]:
        """Busca películas en TMDB por título y, si se indica, por año.

        Solo devuelve la primera página de resultados (hasta 20), que suele
        bastar para encontrar la película buscada. Los errores temporales
        (429 y 5xx) y los fallos de conexión se reintentan hasta
        MAX_RETRIES veces, con una espera creciente entre intentos que
        respeta la cabecera Retry-After si TMDB la envía.

        Args:
            title: Título que se busca.
            year: Año de estreno, o None para buscar sin filtrar por año.

        Returns:
            Lista de resultados de TMDB, cada uno como diccionario con
            campos como id, title, original_title, release_date y
            vote_count. Vacía si no hay resultados.

        Raises:
            requests.HTTPError: Si TMDB responde con un código de error
                que no se reintenta, por ejemplo 401 si el token no es
                válido, o si un error temporal persiste tras los
                reintentos.
            requests.RequestException: Si falla la conexión o se supera
                el tiempo de espera de TIMEOUT segundos en todos los
                intentos.
        """
        response = self.session.get(
            f"{BASE_URL}/search/movie",
            params={"query": title, "primary_release_year": year},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        results: list[dict[str, Any]] = response.json()["results"]
        return results
