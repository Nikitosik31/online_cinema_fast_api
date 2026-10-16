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

