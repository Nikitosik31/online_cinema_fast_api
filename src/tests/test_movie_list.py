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

    async def test_filter_movies_by_nonexistent_genre_returns_empty_list(
        self, client, create_movie
    ):
        await create_movie("Test")
        res = await client.get("/movies/?genre_id=99999")
        assert res.status_code == 200
        data = res.json()
        assert data["movies"] == []
        assert data["total_pages"] == 0
        assert data["total_items"] == 0
        assert data["next_page"] is None
        assert data["prev_page"] is None

    async def test_filter_movies_by_multiple_genre_ids_returns_movies_of_any_genre(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", genres=["Drama"])
        movie2 = await create_movie("Test", genres=["Comedy"])
        await create_movie("Test2", genres=["Horror"])

        res = await client.get(
            f"/movies/?genre_id={movie1['genres'][0]['id']}&genre_id={movie2['genres'][0]['id']}"
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["movies"]) == 2
        ids = {movie["id"] for movie in data["movies"]}
        assert ids == {movie1["id"], movie2["id"]}
        assert data["total_items"] == 2

    async def test_filter_movies_with_both_requested_genres_returns_movie_once(
        self, client, create_movie
    ):
        movie = await create_movie("Test", genres=["Comedy", "Drama"])
        await create_movie("Test2", genres=["Horror"])
        res = await client.get(
            f"/movies/?genre_id={movie['genres'][0]['id']}&genre_id={movie['genres'][1]['id']}"
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["movies"]) == 1
        assert data["total_items"] == 1

    async def test_list_movies_pagination_links_keep_genre_filter(
        self, client, create_movie
    ):
        movie = await create_movie("Movie", genres=["Comedy"])
        await create_movie("Test", genres=["Comedy"])
        await create_movie("Test2", genres=["Comedy"])
        await create_movie("Test3", genres=["Horror"])

        res = await client.get(
            f"/movies/?page=1&per_page=2&genre_id={movie['genres'][0]['id']}"
        )
        assert res.status_code == 200
        data = res.json()
        assert (
            data["next_page"]
            == f"/movies/?page=2&per_page=2&genre_id={movie['genres'][0]['id']}"
        )
        assert data["total_items"] == 3

    async def test_filter_movies_by_year_returns_only_movies_of_that_year(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", year=2020)
        movie2 = await create_movie("Test", year=2020)
        await create_movie("Test2", year=2011)

        res = await client.get(f"/movies/?year={movie1['year']}")
        assert res.status_code == 200
        data = res.json()
        assert len(data["movies"]) == 2
        ids = {movie["id"] for movie in data["movies"]}
        assert ids == {movie1["id"], movie2["id"]}
        assert data["total_items"] == 2

    async def test_filter_movies_by_imdb_min_returns_movies_with_rating_at_least_that(
        self, client, create_movie
    ):
        await create_movie("Movie", imdb=7.5)
        movie1 = await create_movie("Test", imdb=8.0)
        movie2 = await create_movie("Test2", imdb=9.0)

        res = await client.get(f"/movies/?imdb_min={movie1['imdb']}")
        assert res.status_code == 200
        data = res.json()
        assert len(data["movies"]) == 2
        ids = {movie["id"] for movie in data["movies"]}
        assert ids == {movie1["id"], movie2["id"]}
        assert data["total_items"] == 2


class TestSortMovies:
    pass


class TestSearchMovies:
    pass
