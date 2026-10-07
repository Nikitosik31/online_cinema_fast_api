class TestMovieList:
    async def test_list_movies_returns_empty_list_when_no_movies(self, client):
        res = await client.get("/movies/")
        assert res.status_code == 200
        assert res.json() == {
            "movies": [],
            "prev_page": None,
            "next_page": None,
            "total_pages": 0,
            "total_items": 0,
        }

    async def test_list_movies_returns_list_with_one_movie(
        self, client, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.get("/movies/")
        assert res.status_code == 200
        data = res.json()

        assert len(data["movies"]) == 1
        item = data["movies"][0]

        assert item["name"] == movie["name"]
        assert item["id"] == movie["id"]
        assert item["year"] == movie["year"]
        assert item["imdb"] == movie["imdb"]

        assert {genre["name"] for genre in item["genres"]} == {
            genre["name"] for genre in movie["genres"]
        }

        assert "description" not in item
        assert data["prev_page"] is None
        assert data["next_page"] is None
        assert data["total_items"] == 1
        assert data["total_pages"] == 1

    async def test_list_movies_first_page_has_next_page_and_no_prev_page(
        self, client, create_movie
    ):
        for i in range(5):
            await create_movie(f"Movie{i}")

        res_1 = await client.get("/movies/?page=1&per_page=2")
        assert res_1.status_code == 200
        data = res_1.json()
        assert len(data["movies"]) == 2
        assert data["prev_page"] is None
        assert data["next_page"] == "/movies/?page=2&per_page=2"
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

    async def test_list_movies_middle_page_has_prev_and_next_page(
        self, client, create_movie
    ):
        for i in range(5):
            await create_movie(f"Movie{i}")
        res2 = await client.get("/movies/?page=2&per_page=2")
        assert res2.status_code == 200
        data = res2.json()
        assert len(data["movies"]) == 2
        assert data["prev_page"] == "/movies/?page=1&per_page=2"
        assert data["next_page"] == "/movies/?page=3&per_page=2"
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

    async def test_list_movies_last_page_has_prev_and_no_next_page(
        self, client, create_movie
    ):
        for i in range(5):
            await create_movie(f"Movie{i}")

        res = await client.get("/movies/?page=3&per_page=2")
        assert res.status_code == 200
        data = res.json()
        assert len(data["movies"]) == 1
        assert data["prev_page"] == "/movies/?page=2&per_page=2"
        assert data["next_page"] is None
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

    async def test_list_movies_page_out_of_range_returns_empty_list(
        self, client, create_movie
    ):
        for i in range(5):
            await create_movie(f"Movie{i}")

        res = await client.get("/movies/?page=99&per_page=2")
        assert res.status_code == 200
        data = res.json()
        assert data["movies"] == []
        assert data["total_pages"] == 3
        assert data["total_items"] == 5
        assert data["next_page"] is None
        assert data["prev_page"] == "/movies/?page=3&per_page=2"


class TestFilterMovies:
    async def test_filter_movies_by_genre_id(self, client, create_movie):
        movie1 = await create_movie("Movie", genres=["Drama"])
        await create_movie("Test", genres=["Comedy"])

        res = await client.get(
            f"/movies/?genre_id={movie1['genres'][0]['id']}"
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["movies"]) == 1
        assert data["movies"][0]["name"] == movie1["name"]
        assert data["total_items"] == 1
        assert data["total_pages"] == 1


class TestSortMovies:
    pass


class TestSearchMovies:
    pass
