from sqlalchemy import select

from database.models.cart import CartModel, CartItemModel
from database.models.orders import OrderItemModel, OrderStatusEnum, OrderModel
from tests.conftest import test_AsyncPostgresqlSessionLocal
from database.models.movies import MovieModel


class TestCreateOrder:
    async def test_create_order_returns_201(
        self,
        client,
        create_movie,
        create_cart_item,
        create_order,
        active_user_with_token,
    ):
        movie_1 = await create_movie("Movie1", price=150)
        movie_2 = await create_movie("Movie2", price=250)

        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        await create_cart_item(active_user_with_token["id"], movie_2["id"])

        res = await client.post(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        data = res.json()
        order = data["order"]

        assert order["status"] == "pending"
        assert float(order["total_amount"]) == 400
        assert len(order["items"]) == 2
        assert data["excluded_movies"] == []

        prices = {
            item["movie_id"]: float(item["price_at_order"])
            for item in order["items"]
        }
        assert prices == {movie_1["id"]: 150, movie_2["id"]: 250}

        async with test_AsyncPostgresqlSessionLocal() as db:
            db_order = await db.scalar(
                select(OrderModel).where(
                    OrderModel.user_id == active_user_with_token["id"]
                )
            )
            assert db_order is not None
            assert db_order.status == OrderStatusEnum.PENDING

            result = await db.scalars(
                select(OrderItemModel).where(
                    OrderItemModel.order_id == db_order.id
                )
            )
            db_items = result.all()

            db_prices = {
                item.movie_id: float(item.price_at_order) for item in db_items
            }
            assert db_prices == {movie_1["id"]: 150, movie_2["id"]: 250}
            cart = await db.scalar(
                select(CartModel).where(
                    CartModel.user_id == active_user_with_token["id"]
                )
            )
            result = await db.scalars(
                select(CartItemModel).where(CartItemModel.cart_id == cart.id)
            )
            assert len(result.all()) == 2

    async def test_create_order_empty_cart_returns_400(
        self, client, active_user_with_token
    ):
        res = await client.post(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 400

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(select(OrderModel))
            assert result.all() == []

    async def test_create_order_excludes_unavailable_movie(
        self,
        client,
        create_movie,
        create_cart_item,
        active_user_with_token,
    ):
        movie_1 = await create_movie("Movie1", price=150)
        movie_2 = await create_movie("Movie2", price=250)
        await create_cart_item(active_user_with_token["id"], movie_1["id"])
        await create_cart_item(active_user_with_token["id"], movie_2["id"])

        async with test_AsyncPostgresqlSessionLocal() as db:
            db_movie = await db.scalar(
                select(MovieModel).where(MovieModel.id == movie_2["id"])
            )
            db_movie.price = None
            await db.commit()

        res = await client.post(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        data = res.json()
        order = data["order"]
        assert [i["movie_id"] for i in order["items"]] == [movie_1["id"]]
        assert float(order["total_amount"]) == 150
        assert len(data["excluded_movies"]) == 1
        assert data["excluded_movies"][0]["movie_id"] == movie_2["id"]

    async def test_create_order_all_movies_unavailable_returns_400(
        self,
        client,
        create_movie,
        create_cart_item,
        active_user_with_token,
    ):
        movie = await create_movie("Movie1", price=150)
        await create_cart_item(active_user_with_token["id"], movie["id"])

        async with test_AsyncPostgresqlSessionLocal() as db:
            db_movie = await db.scalar(
                select(MovieModel).where(MovieModel.id == movie["id"])
            )
            db_movie.price = None
            await db.commit()

        res = await client.post(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 400

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(select(OrderModel))
            assert result.all() == []

    async def test_create_order_excludes_already_purchased_movie(
        self,
        client,
        create_movie,
        create_cart_item,
        create_order,
        active_user_with_token,
    ):
        movie_a = await create_movie("MovieA", price=100)
        movie_b = await create_movie("MovieB", price=200)
        await create_order(
            active_user_with_token["id"],
            [(movie_a["id"], 100)],
            status=OrderStatusEnum.PAID,
        )
        await create_cart_item(active_user_with_token["id"], movie_a["id"])
        await create_cart_item(active_user_with_token["id"], movie_b["id"])

        res = await client.post(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 201
        data = res.json()
        order = data["order"]
        assert [i["movie_id"] for i in order["items"]] == [movie_b["id"]]
        assert float(order["total_amount"]) == 200
        assert [m["movie_id"] for m in data["excluded_movies"]] == [
            movie_a["id"]
        ]

    async def test_create_order_with_movie_in_pending_order_returns_409(
        self,
        client,
        create_movie,
        create_cart_item,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("MovieA", price=100)
        await create_order(
            active_user_with_token["id"],
            [(movie["id"], 100)],
        )
        await create_cart_item(active_user_with_token["id"], movie["id"])

        res = await client.post(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 409

        async with test_AsyncPostgresqlSessionLocal() as db:
            result = await db.scalars(
                select(OrderModel).where(
                    OrderModel.user_id == active_user_with_token["id"]
                )
            )
            assert len(result.all()) == 1

    async def test_create_order_without_token_returns_401(
        self, client, create_movie, create_cart_item, active_user_with_token
    ):
        movie = await create_movie("Movie1", price=150)
        await create_cart_item(active_user_with_token["id"], movie["id"])
        res = await client.post("/orders/")
        assert res.status_code == 401
