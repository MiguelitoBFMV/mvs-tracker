import requests


class AniListClient:
    API_URL = "https://graphql.anilist.co"

    def fetch_anime_by_mal_id(self, mal_id):
        query = """
        query ($malId: Int!) {
            Media(idMal: $malId, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                status
                episodes
                nextAiringEpisode {
                    episode
                    airingAt
                    timeUntilAiring
                }
                airingSchedule(notYetAired: true, perPage: 5) {
                    nodes {
                        episode
                        airingAt
                        timeUntilAiring
                    }
                }
                externalLinks {
                    site
                    url
                    type
                    language
                }
                streamingEpisodes {
                    title
                    thumbnail
                    url
                    site
                }
            }
        }
        """

        response = requests.post(
            self.API_URL,
            json={
                "query": query,
                "variables": {
                    "malId": mal_id,
                },
            },
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"AniList API error {response.status_code}: {response.text}"
            )

        payload = response.json()

        if "errors" in payload:
            raise Exception(payload["errors"])

        return payload.get("data", {}).get("Media")
    

    def search_anime(self, search):
        query = """
        query ($search: String!) {
            Media(search: $search, type: ANIME) {
                id
                idMal
                title {
                    romaji
                    english
                    native
                }
                status
                episodes
                nextAiringEpisode {
                    episode
                    airingAt
                    timeUntilAiring
                }
            }
        }
        """

        response = requests.post(
            self.API_URL,
            json={
                "query": query,
                "variables": {
                    "search": search,
                },
            },
            timeout=30,
        )

        if not response.ok:
            raise Exception(
                f"AniList API error {response.status_code}: {response.text}"
            )

        payload = response.json()

        if "errors" in payload:
            raise Exception(payload["errors"])

        return payload.get("data", {}).get("Media")