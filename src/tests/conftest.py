from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from config.config import Settings, BASE_DIR
from database.database import Base
from database.models.accounts import (
    UserGroupEnum,
    UserGroupModel,
    UserModel,
    ActivationTokenModel,
)
from httpx import AsyncClient, ASGITransport

from database.models.cart import CartModel, CartItemModel
from database.models.interactions import CommentModel, NotificationModel
from database.models.movies import CertificationEnum, CertificationModel
from database.models.orders import OrderItemModel, OrderModel, OrderStatusEnum
from main import app
from database.database import get_postgresql_db
from security import passwords

test_settings = Settings(_env_file=BASE_DIR / ".env.test")


test_engine = create_async_engine(test_settings.postgres_url)

test_AsyncPostgresqlSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_AsyncPostgresqlSessionLocal() as session:
        for group_enum in UserGroupEnum:
            existing_group = await session.scalar(
                select(UserGroupModel).where(UserGroupModel.name == group_enum)
            )
            if not existing_group:
                group = UserGroupModel(name=group_enum)
                session.add(group)
                await session.commit()

        for certification in CertificationEnum:
            existing_certification = await session.scalar(
                select(CertificationModel).where(
                    CertificationModel.name == certification
                )
            )
            if not existing_certification:
                sertificat = CertificationModel(name=certification)
                session.add(sertificat)
                await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with test_AsyncPostgresqlSessionLocal() as session:
        yield session


app.dependency_overrides[get_postgresql_db] = override_get_db


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def active_user(client):
    email = "active_user_fixture@test.com"
    password = "Testtest1!"

    response = await client.post(
        "/register/", json={"email": email, "password": password}
    )
    user_id = response.json()["id"]

    async with test_AsyncPostgresqlSessionLocal() as session:
        token_obj = await session.scalar(
            select(ActivationTokenModel).where(
                ActivationTokenModel.user_id == user_id
            )
        )
        await client.post("/activate/", json={"token": token_obj.token})

    return {"email": email, "password": password, "id": user_id}


@pytest.fixture
async def active_user_with_token(client, active_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": active_user["email"],
            "password": active_user["password"],
        },
    )
    access_token = login_res.json()["access_token"]

    return {
        "email": active_user["email"],
        "password": active_user["password"],
        "id": active_user["id"],
        "access_token": access_token,
    }


@pytest.fixture(autouse=True)
async def clean_tables():
    yield
    async with test_AsyncPostgresqlSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in ("user_groups", "certifications"):
                await session.execute(table.delete())
                await session.commit()


@pytest.fixture
async def admin_user(client):
    email = "Admin@admin.com"
    password = "Admin!1Admin"

    async with test_AsyncPostgresqlSessionLocal() as session:

        stmt = select(UserGroupModel).where(
            UserGroupModel.name == UserGroupEnum.ADMIN
        )
        admin = await session.scalar(stmt)
        admin_user = UserModel(
            email=email,
            hashed_password=passwords.hash_password(password),
            is_active=True,
            group=admin,
        )

        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)

        return {
            "email": admin_user.email,
            "password": password,
            "id": admin_user.id,
        }


@pytest.fixture
async def moderator_user(client):
    email = "Moderator@admin.com"
    password = "Admin!1Admin"

    async with test_AsyncPostgresqlSessionLocal() as session:

        stmt = select(UserGroupModel).where(
            UserGroupModel.name == UserGroupEnum.MODERATOR
        )
        moderator = await session.scalar(stmt)
        moderator_user = UserModel(
            email=email,
            hashed_password=passwords.hash_password(password),
            is_active=True,
            group=moderator,
        )

        session.add(moderator_user)
        await session.commit()
        await session.refresh(moderator_user)

        login_res = await client.post(
            "/login/",
            json={"email": email, "password": password},
        )
        access_token = login_res.json()["access_token"]

        return {
            "email": moderator_user.email,
            "password": password,
            "id": moderator_user.id,
            "access_token": access_token,
        }


@pytest.fixture
async def existing_genre(client, moderator_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": moderator_user["email"],
            "password": moderator_user["password"],
        },
    )
    access_token = login_res.json()["access_token"]

    create_res = await client.post(
        "/movies/genres/",
        json={"name": "Documentary"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    return {
        "id": create_res.json()["id"],
        "name": "Documentary",
        "access_token": access_token,
    }


@pytest.fixture
async def existing_star(client, moderator_user):
    login_res = await client.post(
        "/login/",
        json={
            "email": moderator_user["email"],
            "password": moderator_user["password"],
        },
    )
    access_token = login_res.json()["access_token"]

    create_res = await client.post(
        "/movies/stars/",
        json={"name": "Brad Pitt"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    return {
        "id": create_res.json()["id"],
        "name": "Brad Pitt",
        "access_token": access_token,
    }


@pytest.fixture
async def existing_movie(client, moderator_user):
    async with test_AsyncPostgresqlSessionLocal() as session:
        certification = await session.scalar(
            select(CertificationModel).where(
                CertificationModel.name == CertificationEnum.G
            )
        )
    login_res = await client.post(
        "/login/",
        json={
            "email": moderator_user["email"],
            "password": moderator_user["password"],
        },
    )
    access_token = login_res.json()["access_token"]

    movie_res = await client.post(
        "/movies/",
        json={
            "name": "Inception",
            "year": 2010,
            "time": 148,
            "imdb": 8.8,
            "votes": 2000000,
            "description": "A thief who steals corporate secrets...",
            "certification_id": certification.id,
            "genres": ["Sci-Fi", "Action"],
            "directors": ["Christopher Nolan"],
            "stars": ["Leonardo DiCaprio"],
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    data = movie_res.json()
    return {
        "id": data["id"],
        "name": data["name"],
        "year": data["year"],
        "time": data["time"],
        "access_token": access_token,
        "certification_id": data["certification"]["id"],
    }


@pytest.fixture
async def create_movie(client, moderator_user):
    async with test_AsyncPostgresqlSessionLocal() as session:
        certification = await session.scalar(
            select(CertificationModel).where(
                CertificationModel.name == CertificationEnum.G
            )
        )
    login_res = await client.post(
        "/login/",
        json={
            "email": moderator_user["email"],
            "password": moderator_user["password"],
        },
    )
    access_token = login_res.json()["access_token"]

    async def _create(
        name,
        year=2010,
        time=148,
        imdb=8.8,
        votes=2000000,
        description="A thief who steals corporate secrets...",
        certification_id=certification.id,
        genres=None,
        directors=None,
        stars=None,
        price=None,
    ):

        if genres is None:
            genres = ["Sci-Fi", "Action"]

        if directors is None:
            directors = ["Christopher Nolan"]

        if stars is None:
            stars = ["Leonardo DiCaprio"]

        movie_res = await client.post(
            "/movies/",
            json={
                "name": name,
                "year": year,
                "time": time,
                "imdb": imdb,
                "votes": votes,
                "description": description,
                "certification_id": certification_id,
                "genres": genres,
                "directors": directors,
                "stars": stars,
                "price": price,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        data = movie_res.json()
        return {
            "id": data["id"],
            "name": data["name"],
            "year": data["year"],
            "time": data["time"],
            "imdb": data["imdb"],
            "votes": data["votes"],
            "description": data["description"],
            "genres": data["genres"],
            "directors": data["directors"],
            "stars": data["stars"],
            "price": data["price"],
        }

    return _create


@pytest.fixture
async def create_comment():
    async def _create(
        movie_id,
        user_id,
        content="Nice movie",
        created_at=None,
        parent_id=None,
    ):
        kwargs = {"movie_id": movie_id, "user_id": user_id, "content": content}
        if created_at is not None:
            kwargs["created_at"] = created_at
        if parent_id is not None:
            kwargs["parent_id"] = parent_id

        async with test_AsyncPostgresqlSessionLocal() as session:
            comment = CommentModel(**kwargs)
            session.add(comment)
            await session.commit()
            await session.refresh(comment)

            return {
                "id": comment.id,
                "movie_id": comment.movie_id,
                "user_id": comment.user_id,
                "content": comment.content,
                "created_at": comment.created_at,
                "parent_id": comment.parent_id,
            }

    return _create


@pytest.fixture
async def create_notification():
    async def _create(
        recipient_id,
        sender_id,
        comment_id,
        notification_type,
        is_read=False,
        created_at=None,
    ):
        kwargs = {
            "recipient_id": recipient_id,
            "sender_id": sender_id,
            "comment_id": comment_id,
            "notification_type": notification_type,
            "is_read": is_read,
        }
        if created_at is not None:
            kwargs["created_at"] = created_at

        async with test_AsyncPostgresqlSessionLocal() as session:
            notification = NotificationModel(**kwargs)
            session.add(notification)
            await session.commit()
            await session.refresh(notification)

            return {
                "id": notification.id,
                "recipient_id": notification.recipient_id,
                "sender_id": notification.sender_id,
                "comment_id": notification.comment_id,
                "notification_type": notification.notification_type,
                "is_read": notification.is_read,
                "created_at": notification.created_at,
            }

    return _create


@pytest.fixture
async def create_cart_item():
    async def _create(
        user_id,
        movie_id,
        added_at=None,
    ):

        async with test_AsyncPostgresqlSessionLocal() as session:
            user_cart = await session.scalar(
                select(CartModel).where(CartModel.user_id == user_id)
            )
            if not user_cart:
                user_cart = CartModel(user_id=user_id)
                session.add(user_cart)
                await session.flush()

            kwargs = {"cart_id": user_cart.id, "movie_id": movie_id}
            if added_at is not None:
                kwargs["added_at"] = added_at

            cart_items = CartItemModel(**kwargs)
            session.add(cart_items)
            await session.commit()
            await session.refresh(cart_items)

        return {
            "id": cart_items.id,
            "cart_id": user_cart.id,
            "user_id": user_id,
            "movie_id": movie_id,
            "added_at": cart_items.added_at,
        }

    return _create


@pytest.fixture
async def create_order():
    async def _create(
        user_id,
        movies,
        status=OrderStatusEnum.PENDING,
        created_at=None,
    ):
        total = sum((Decimal(str(price)) for _, price in movies), Decimal("0"))

        kwargs = {
            "user_id": user_id,
            "status": status,
            "total_amount": total,
        }
        if created_at is not None:
            kwargs["created_at"] = created_at

        async with test_AsyncPostgresqlSessionLocal() as session:
            order = OrderModel(**kwargs)
            session.add(order)
            await session.flush()

            items = []
            for movie_id, price in movies:
                item = OrderItemModel(
                    order_id=order.id,
                    movie_id=movie_id,
                    price_at_order=Decimal(str(price)),
                )
                session.add(item)
                items.append(item)

            await session.commit()
            await session.refresh(order)

            return {
                "id": order.id,
                "user_id": order.user_id,
                "status": order.status,
                "total_amount": order.total_amount,
                "created_at": order.created_at,
                "items": [
                    {
                        "movie_id": movie_id,
                        "price_at_order": Decimal(str(price)),
                    }
                    for movie_id, price in movies
                ],
            }

    return _create


@pytest.fixture(autouse=True)
def mock_send_user(monkeypatch):
    monkeypatch.setattr("routes.accounts.send_email", AsyncMock())
