import pytest

DOCS_URLS = ["/docs", "/redoc", "/openapi.json"]


@pytest.mark.parametrize("url", DOCS_URLS)
class TestDocsAccess:
    async def test_no_credentials_returns_401(self, client, url):
        res = await client.get(url)

        assert res.status_code == 401
        assert res.headers["www-authenticate"] == "Basic"

    async def test_wrong_password_returns_401(
        self, client, moderator_user, url
    ):
        res = await client.get(
            url, auth=(moderator_user["email"], "Wrong!1Password")
        )

        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid email or password"

    async def test_unknown_email_returns_the_same_401(self, client, url):
        res = await client.get(
            url, auth=("nobody@test.com", "Wrong!1Password")
        )

        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid email or password"

    async def test_inactive_user_returns_401(self, client, url):
        email = "inactive@test.com"
        password = "Testtest1!"
        await client.post(
            "/register/", json={"email": email, "password": password}
        )

        res = await client.get(url, auth=(email, password))

        assert res.status_code == 401

    async def test_regular_user_returns_403(self, client, active_user, url):
        res = await client.get(
            url, auth=(active_user["email"], active_user["password"])
        )

        assert res.status_code == 403

    async def test_moderator_returns_200(self, client, moderator_user, url):
        res = await client.get(
            url, auth=(moderator_user["email"], moderator_user["password"])
        )

        assert res.status_code == 200

    async def test_admin_returns_200(self, client, admin_user, url):
        res = await client.get(
            url, auth=(admin_user["email"], admin_user["password"])
        )

        assert res.status_code == 200


class TestDocsContent:
    async def test_openapi_schema_describes_the_api(
        self, client, moderator_user
    ):
        res = await client.get(
            "/openapi.json",
            auth=(moderator_user["email"], moderator_user["password"]),
        )

        data = res.json()
        assert data["info"]["title"] == "Online Cinema API"
        assert "/login/" in data["paths"]

    async def test_docs_routes_are_not_listed_in_the_schema(
        self, client, moderator_user
    ):
        res = await client.get(
            "/openapi.json",
            auth=(moderator_user["email"], moderator_user["password"]),
        )

        paths = res.json()["paths"]
        assert "/docs" not in paths
        assert "/redoc" not in paths
        assert "/openapi.json" not in paths

    @pytest.mark.parametrize("url", ["/docs", "/redoc"])
    async def test_pages_load_the_protected_schema(
        self, client, moderator_user, url
    ):
        res = await client.get(
            url, auth=(moderator_user["email"], moderator_user["password"])
        )

        assert "Online Cinema API" in res.text
        assert "/openapi.json" in res.text
