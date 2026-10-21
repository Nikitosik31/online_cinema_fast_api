from sqlalchemy import select
from datetime import datetime

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


class TestListOrders:
    async def test_list_orders_empty_returns_empty_list(
        self, client, active_user_with_token
    ):
        res = await client.get(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["orders"] == []
        assert data["total_items"] == 0
        assert data["total_pages"] == 0
        assert data["prev_page"] is None
        assert data["next_page"] is None

    async def test_list_orders_returns_my_orders_newest_first(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie_a = await create_movie("MovieA", price=100)
        movie_b = await create_movie("MovieB", price=200)
        movie_c = await create_movie("MovieC", price=300)

        older = await create_order(
            active_user_with_token["id"],
            [(movie_a["id"], 100), (movie_b["id"], 200)],
            status=OrderStatusEnum.PAID,
            created_at=datetime(2024, 1, 1),
        )
        newer = await create_order(
            active_user_with_token["id"],
            [(movie_c["id"], 300)],
            created_at=datetime(2024, 1, 3),
        )

        res = await client.get(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert [o["id"] for o in data["orders"]] == [newer["id"], older["id"]]
        assert data["total_items"] == 2

        by_id = {o["id"]: o for o in data["orders"]}
        old = by_id[older["id"]]
        assert old["status"] == "paid"
        assert float(old["total_amount"]) == 300
        assert {i["movie_id"] for i in old["items"]} == {
            movie_a["id"],
            movie_b["id"],
        }
        assert {i["name"] for i in old["items"]} == {"MovieA", "MovieB"}

        new = by_id[newer["id"]]
        assert new["status"] == "pending"
        assert float(new["total_amount"]) == 300
        assert [i["movie_id"] for i in new["items"]] == [movie_c["id"]]

    async def test_list_orders_shows_only_my_orders(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        moderator_user,
    ):
        movie_a = await create_movie("MovieA", price=100)
        movie_b = await create_movie("MovieB", price=200)
        mine = await create_order(
            active_user_with_token["id"], [(movie_a["id"], 100)]
        )
        await create_order(moderator_user["id"], [(movie_b["id"], 200)])

        res = await client.get(
            "/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert [o["id"] for o in data["orders"]] == [mine["id"]]
        assert data["total_items"] == 1

    async def test_list_orders_pagination_links(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie", price=100)
        for _ in range(5):
            await create_order(
                active_user_with_token["id"], [(movie["id"], 100)]
            )
        headers = {
            "Authorization": f"Bearer {active_user_with_token['access_token']}"
        }

        res1 = await client.get("/orders/?page=1&per_page=2", headers=headers)
        assert res1.status_code == 200
        data = res1.json()
        assert len(data["orders"]) == 2
        assert data["prev_page"] is None
        assert data["next_page"] == "/orders/?page=2&per_page=2"
        assert data["total_pages"] == 3
        assert data["total_items"] == 5

        res2 = await client.get("/orders/?page=2&per_page=2", headers=headers)
        data = res2.json()
        assert len(data["orders"]) == 2
        assert data["prev_page"] == "/orders/?page=1&per_page=2"
        assert data["next_page"] == "/orders/?page=3&per_page=2"

        res3 = await client.get("/orders/?page=3&per_page=2", headers=headers)
        data = res3.json()
        assert len(data["orders"]) == 1
        assert data["prev_page"] == "/orders/?page=2&per_page=2"
        assert data["next_page"] is None

    async def test_list_orders_page_out_of_range_returns_empty_list(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
    ):
        movie = await create_movie("Movie", price=100)
        await create_order(active_user_with_token["id"], [(movie["id"], 100)])

        res = await client.get(
            "/orders/?page=99&per_page=2",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["orders"] == []
        assert data["total_items"] == 1
        assert data["total_pages"] == 1
        assert data["next_page"] is None
        assert data["prev_page"] == "/orders/?page=1&per_page=2"

    async def test_list_orders_without_token_returns_401(self, client):
        res = await client.get("/orders/")
        assert res.status_code == 401


class TestCancelOrder:
    async def test_cancel_pending_order_returns_200(
        self, client, create_movie, create_order, active_user_with_token
    ):
        movie = await create_movie("Movie", price=100)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 100)]
        )

        res = await client.post(
            f"/orders/{order['id']}/cancel/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 200
        assert res.json()["status"] == "canceled"

        async with test_AsyncPostgresqlSessionLocal() as db:
            db_order = await db.scalar(
                select(OrderModel).where(OrderModel.id == order["id"])
            )
            assert db_order.status == OrderStatusEnum.CANCELED

    async def test_cancel_paid_order_returns_409(
        self, client, create_movie, create_order, active_user_with_token
    ):
        movie = await create_movie("Movie", price=100)
        order = await create_order(
            active_user_with_token["id"],
            [(movie["id"], 100)],
            status=OrderStatusEnum.PAID,
        )

        res = await client.post(
            f"/orders/{order['id']}/cancel/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 409

        async with test_AsyncPostgresqlSessionLocal() as db:
            db_order = await db.scalar(
                select(OrderModel).where(OrderModel.id == order["id"])
            )
            assert db_order.status == OrderStatusEnum.PAID

    async def test_cancel_already_canceled_order_returns_409(
        self, client, create_movie, create_order, active_user_with_token
    ):
        movie = await create_movie("Movie", price=100)
        order = await create_order(
            active_user_with_token["id"],
            [(movie["id"], 100)],
            status=OrderStatusEnum.CANCELED,
        )

        res = await client.post(
            f"/orders/{order['id']}/cancel/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 409

    async def test_cancel_order_not_found_returns_404(
        self, client, active_user_with_token
    ):
        res = await client.post(
            "/orders/99999/cancel/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

    async def test_cancel_other_users_order_returns_404(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie", price=100)
        order = await create_order(moderator_user["id"], [(movie["id"], 100)])

        res = await client.post(
            f"/orders/{order['id']}/cancel/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 404

        async with test_AsyncPostgresqlSessionLocal() as db:
            db_order = await db.scalar(
                select(OrderModel).where(OrderModel.id == order["id"])
            )
            assert db_order.status == OrderStatusEnum.PENDING

    async def test_cancel_order_without_token_returns_401(
        self, client, create_movie, create_order, active_user_with_token
    ):
        movie = await create_movie("Movie", price=100)
        order = await create_order(
            active_user_with_token["id"], [(movie["id"], 100)]
        )
        res = await client.post(f"/orders/{order['id']}/cancel/")
        assert res.status_code == 401


class TestModeratorListOrders:
    async def test_moderator_lists_all_orders(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        moderator_user,
    ):
        movie_a = await create_movie("MovieA", price=100)
        movie_b = await create_movie("MovieB", price=200)
        order_user = await create_order(
            active_user_with_token["id"], [(movie_a["id"], 100)]
        )
        order_moderator = await create_order(
            moderator_user["id"], [(movie_b["id"], 200)]
        )

        res = await client.get(
            "/moderator/orders/",
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert {o["id"] for o in data["orders"]} == {
            order_user["id"],
            order_moderator["id"],
        }
        assert data["total_items"] == 2

    async def test_moderator_filters_orders_by_user(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie", price=100)
        order_user = await create_order(
            active_user_with_token["id"], [(movie["id"], 100)]
        )
        await create_order(moderator_user["id"], [(movie["id"], 100)])

        res = await client.get(
            f"/moderator/orders/?user_id={active_user_with_token['id']}",
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert [o["id"] for o in data["orders"]] == [order_user["id"]]
        assert data["total_items"] == 1

    async def test_moderator_filters_orders_by_status(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        moderator_user,
    ):
        movie_a = await create_movie("MovieA", price=100)
        movie_b = await create_movie("MovieB", price=200)
        await create_order(
            active_user_with_token["id"], [(movie_a["id"], 100)]
        )
        paid = await create_order(
            active_user_with_token["id"],
            [(movie_b["id"], 200)],
            status=OrderStatusEnum.PAID,
        )

        res = await client.get(
            "/moderator/orders/?status=paid",
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert [o["id"] for o in data["orders"]] == [paid["id"]]

    async def test_moderator_filters_orders_by_date(
        self,
        client,
        create_movie,
        create_order,
        active_user_with_token,
        moderator_user,
    ):
        movie = await create_movie("Movie", price=100)
        await create_order(
            active_user_with_token["id"],
            [(movie["id"], 100)],
            created_at=datetime(2024, 1, 1),
        )
        middle = await create_order(
            active_user_with_token["id"],
            [(movie["id"], 100)],
            created_at=datetime(2024, 1, 5),
        )
        await create_order(
            active_user_with_token["id"],
            [(movie["id"], 100)],
            created_at=datetime(2024, 1, 10),
        )

        res = await client.get(
            "/moderator/orders/?date_from=2024-01-03&date_to=2024-01-08",
            headers={
                "Authorization": f"Bearer {moderator_user['access_token']}"
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert [o["id"] for o in data["orders"]] == [middle["id"]]

    async def test_regular_user_cannot_list_all_orders_returns_403(
        self, client, active_user_with_token
    ):
        res = await client.get(
            "/moderator/orders/",
            headers={
                "Authorization": f"Bearer {active_user_with_token['access_token']}"
            },
        )
        assert res.status_code == 403

    async def test_moderator_list_orders_without_token_returns_401(
        self, client
    ):
        res = await client.get("/moderator/orders/")
        assert res.status_code == 401
