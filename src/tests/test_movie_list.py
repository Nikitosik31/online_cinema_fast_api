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
    async def test_sort_movies_by_year_desc_returns_newest_first(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", year=2010)
        movie2 = await create_movie("Test", year=2000)
        movie3 = await create_movie("Test2", year=2020)

        res = await client.get("/movies/?sort_by=year&order=desc")
        assert res.status_code == 200
        data = res.json()
        years = [movie["year"] for movie in data["movies"]]
        assert years == [movie3["year"], movie1["year"], movie2["year"]]

    async def test_sort_movies_by_year_asc_returns_oldest_first(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", year=2010)
        movie2 = await create_movie("Test", year=2000)
        movie3 = await create_movie("Test2", year=2020)

        res = await client.get("/movies/?sort_by=year&order=asc")
        assert res.status_code == 200
        data = res.json()
        years = [movie["year"] for movie in data["movies"]]
        assert years == [movie2["year"], movie1["year"], movie3["year"]]

    async def test_sort_movies_by_votes_desc_returns_most_popular_first(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", votes=5000)
        movie2 = await create_movie("Test", votes=500)
        movie3 = await create_movie("Test2", votes=50000)

        res = await client.get("/movies/?sort_by=votes&order=desc")
        assert res.status_code == 200
        data = res.json()
        movies_id = [movie["id"] for movie in data["movies"]]
        assert movies_id == [movie3["id"], movie1["id"], movie2["id"]]

    async def test_sort_movies_by_price_asc_returns_cheapest_first(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", price=100)
        movie2 = await create_movie("Test", price=300)
        movie3 = await create_movie("Test2", price=200)

        res = await client.get("/movies/?sort_by=price&order=asc")
        assert res.status_code == 200
        data = res.json()
        movies_id = [movie["id"] for movie in data["movies"]]
        assert movies_id == [movie1["id"], movie3["id"], movie2["id"]]

    async def test_sort_movies_with_unknown_sort_by_returns_422(
        self, client, create_movie
    ):
        res = await client.get(f"/movies/?sort_by=unknown&order=asc")
        assert res.status_code == 422
        data = res.json()
        assert "detail" in data

    async def test_list_movies_pagination_links_keep_sort_params(
        self, client, create_movie
    ):
        await create_movie("Movie", year=2010)
        await create_movie("Test", year=2020)
        await create_movie("Test2", year=2000)

        res = await client.get(
            f"/movies/?page=1&per_page=2&sort_by=year&order=desc"
        )
        assert res.status_code == 200
        data = res.json()
        assert (
            data["next_page"]
            == "/movies/?page=2&per_page=2&sort_by=year&order=desc"
        )


class TestSearchMovies:
    async def test_search_movies_by_title_returns_matching_movies(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie")
        await create_movie("Test")
        await create_movie("Test2")

        res = await client.get("/movies/?search=MO")
        assert res.status_code == 200
        data = res.json()
        assert data["movies"][0]["name"] == movie1["name"]
        assert data["total_items"] == 1

    async def test_search_movies_by_star_name_returns_matching_movies(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", stars=["Tom HANKS"])
        await create_movie("Test", stars=["Brad Pitt"])
        res = await client.get("/movies/?search=hank")
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie1["id"]]
        assert data["total_items"] == 1

    async def test_search_movies_by_director_name_returns_matching_movies(
        self, client, create_movie
    ):
        movie1 = await create_movie("Movie", directors=["Steven Spielberg"])
        await create_movie("Test", directors=["Quentin Tarantino"])
        res = await client.get("/movies/?search=Spi")
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie1["id"]]
        assert data["total_items"] == 1

    async def test_search_movies_by_descriptions_returns_matching_movies(
        self, client, create_movie
    ):
        movie1 = await create_movie(
            "Movie", description="LAlalalal lala,slcla m"
        )
        await create_movie("Test", description="TututuTTTYU")
        res = await client.get("/movies/?search=lal")
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie1["id"]]
        assert data["total_items"] == 1

    async def test_search_movies_with_no_matches_returns_empty_list(
        self, client, create_movie
    ):
        await create_movie("Movie")
        res = await client.get("/movies/?search=zzzzz")
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == []
        assert data["total_items"] == 0

    async def test_search_movies_matching_several_fields_returns_movie_once(
        self, client, create_movie
    ):
        movie1 = await create_movie(
            "Movie",
            stars=["MoShehi"],
            directors=["Monstr"],
            description="Monday",
        )
        res = await client.get("/movies/?search=mo")
        assert res.status_code == 200
        data = res.json()
        ids = [movie["id"] for movie in data["movies"]]
        assert ids == [movie1["id"]]
        assert data["total_items"] == 1
