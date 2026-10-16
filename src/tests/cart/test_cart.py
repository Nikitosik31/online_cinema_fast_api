from sqlalchemy import select

from database.models.cart import CartItemModel, CartModel
from tests.conftest import test_AsyncPostgresqlSessionLocal


class TestAddToCart:
    async def test_add_movie_to_cart_returns_201(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie", price=345)
        res = await client.post(
            "/cart/items/",
            json={
                "movie_id": movie["id"],
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        async with test_AsyncPostgresqlSessionLocal() as db:
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart is not None

            stmt = await db.scalars(
                select(CartItemModel).where(
                    CartItemModel.movie_id == movie["id"],
                    CartItemModel.cart_id == cart.id,
                )
            )

            items = stmt.all()
            assert len(items) == 1

    async def test_add_two_movies_creates_one_cart(
        self, client, create_movie, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=345)
        movie_2 = await create_movie("Movie2", price=346)
        res1 = await client.post(
            "/cart/items/",
            json={
                "movie_id": movie_1["id"],
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res1.status_code == 201

        res2 = await client.post(
            "/cart/items/",
            json={
                "movie_id": movie_2["id"],
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res2.status_code == 201

        async with test_AsyncPostgresqlSessionLocal() as db:
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart is not None

            stmt = await db.scalars(
                select(CartItemModel).where(CartItemModel.cart_id == cart.id)
            )
            items = stmt.all()
            assert len(items) == 2

    async def test_add_movie_to_cart_twice_returns_409(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie", price=345)
        res = await client.post(
            "/cart/items/",
            json={
                "movie_id": movie["id"],
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        res_2 = await client.post(
            "/cart/items/",
            json={
                "movie_id": movie["id"],
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res_2.status_code == 409
        async with test_AsyncPostgresqlSessionLocal() as db:
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart is not None
            stmt = await db.scalars(
                select(CartItemModel).where(CartItemModel.cart_id == cart.id)
            )
            items = stmt.all()
            assert len(items) == 1

    async def test_add_movie_to_cart_movie_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res = await client.post(
            "/cart/items/",
            json={
                "movie_id": 99999,
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_add_movie_without_price_returns_400(
        self, client, create_movie, active_user_with_token
    ):
        movie = await create_movie("Movie", price=None)
        res = await client.post(
            "/cart/items/",
            json={
                "movie_id": movie["id"],
            },
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 400

        async with test_AsyncPostgresqlSessionLocal() as db:
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart is None

    async def test_add_movie_to_cart_without_token_returns_401(
        self, client, create_movie
    ):
        movie = await create_movie("Movie", price=100)
        res = await client.post(
            "/cart/items/",
            json={
                "movie_id": movie["id"],
            },
        )
        assert res.status_code == 401

    async def test_add_movie_to_cart_invalid_body_returns_422(
        self, client, active_user_with_token
    ):
        res = await client.post(
            "/cart/items/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 422


class TestGetCart:
    async def test_get_empty_cart_returns_empty_list(
        self, client, active_user_with_token
    ):
        res = await client.get(
            "/cart/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["items"] == []
        assert data["total_items"] == 0
        assert float(data["total_price"]) == 0

        async with test_AsyncPostgresqlSessionLocal() as db:
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart is None

    async def test_get_cart_returns_items(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=150)
        movie_2 = await create_movie("Movie2", price=250)

        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        await create_cart_item(active_user_with_token["id"], movie_2["id"])
        res = await client.get(
            "/cart/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_items"] == 2
        assert float(data["total_price"]) == 400
        by_id = {item["movie_id"]: item for item in data["items"]}
        assert float(by_id[movie_1["id"]]["price"]) == 150
        assert by_id[movie_1["id"]]["name"] == movie_1["name"]
        assert by_id[movie_1["id"]]["year"] == movie_1["year"]
        assert {g["name"] for g in by_id[movie_1["id"]]["genres"]} == {
            g["name"] for g in movie_1["genres"]
        }

    async def test_get_cart_shows_only_my_items(
        self,
        client,
        create_movie,
        create_cart_item,
        active_user_with_token,
        moderator_user,
    ):
        movie_1 = await create_movie("Movie", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        await create_cart_item(moderator_user["id"], movie_2["id"])

        res = await client.get(
            "/cart/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total_items"] == 1

    async def test_get_cart_without_token_returns_401(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=150)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        res = await client.get(
            "/cart/",
        )
        assert res.status_code == 401


class TestRemoveFromCart:
    async def test_remove_movie_from_cart_returns_204(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=150)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])

        res = await client.delete(
            f"/cart/items/{movie_1['id']}/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 204

        async with test_AsyncPostgresqlSessionLocal() as db:
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart is not None

            stmt = await db.scalars(
                select(CartItemModel).where(CartItemModel.cart_id == cart.id)
            )
            items = stmt.all()

            assert len(items) == 0

    async def test_remove_movie_not_in_cart_returns_404(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=150)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        res = await client.delete(
            f"/cart/items/99999/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_remove_movie_does_not_touch_other_users_cart(
        self,
        client,
        create_movie,
        create_cart_item,
        active_user_with_token,
        moderator_user,
    ):
        movie_1 = await create_movie("Movie", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        await create_cart_item(moderator_user["id"], movie_2["id"])

        res = await client.delete(
            f"/cart/items/{movie_1['id']}/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 204
        async with test_AsyncPostgresqlSessionLocal() as db:
            cart_user = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart_user is not None

            stmt = await db.scalars(
                select(CartItemModel).where(
                    CartItemModel.cart_id == cart_user.id
                )
            )
            items_users = stmt.all()
            assert len(items_users) == 0

            cart_other_user = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == moderator_user["id"]
                )
            )
            assert cart_other_user is not None

            stmt = await db.scalars(
                select(CartItemModel).where(
                    CartItemModel.cart_id == cart_other_user.id
                )
            )
            items_other_users = stmt.all()
            assert len(items_other_users) == 1

    async def test_remove_movie_from_cart_without_token_returns_401(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=150)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        res = await client.delete(
            f"/cart/items/{movie_1['id']}/",
        )
        assert res.status_code == 401


class TestClearCart:
    async def test_clear_cart_returns_204(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        await create_cart_item(active_user_with_token["id"], movie_2["id"])
        res = await client.delete(
            "/cart/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 204
        async with test_AsyncPostgresqlSessionLocal() as db:
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart is not None

            stmt = await db.scalars(
                select(CartItemModel).where(CartItemModel.cart_id == cart.id)
            )
            items = stmt.all()
            assert len(items) == 0

    async def test_clear_empty_cart_returns_204(
        self, client, active_user_with_token
    ):
        res = await client.delete(
            "/cart/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 204

    async def test_clear_cart_does_not_touch_other_users_cart(
        self,
        client,
        create_movie,
        create_cart_item,
        active_user_with_token,
        moderator_user,
    ):
        movie_1 = await create_movie("Movie", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        movie_3 = await create_movie("Movie3", price=300)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        await create_cart_item(active_user_with_token["id"], movie_2["id"])
        await create_cart_item(moderator_user["id"], movie_3["id"])

        res = await client.delete(
            "/cart/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 204

        async with test_AsyncPostgresqlSessionLocal() as db:
            cart_user = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            assert cart_user is not None

            stmt = await db.scalars(
                select(CartItemModel).where(
                    CartItemModel.cart_id == cart_user.id
                )
            )
            items = stmt.all()
            assert len(items) == 0

            cart_other_user = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == moderator_user["id"]
                )
            )
            assert cart_other_user is not None
            stmt = await db.scalars(
                select(CartItemModel).where(
                    CartItemModel.cart_id == cart_other_user.id
                )
            )
            items = stmt.all()
            assert len(items) == 1

    async def test_clear_cart_without_token_returns_401(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie_1 = await create_movie("Movie", price=150)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        res = await client.delete(
            "/cart/",
        )
        assert res.status_code == 401
