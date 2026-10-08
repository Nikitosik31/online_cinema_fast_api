from sqlalchemy import select

from database.models.interactions import FavoriteMovie
from tests.conftest import test_AsyncPostgresqlSessionLocal


class TestAddFavorite:
    async def test_add_movie_to_favorites_returns_201(
        self, client, active_user, create_movie
    ):
        movie = await create_movie("Movie")
        res = await client.post(
            f"/movies/{movie.id}/favorite",
            headers={"Authorization": f"Bearer {active_user['access_token']}"},
        )
        assert res.status_code == 201

        async with test_AsyncPostgresqlSessionLocal() as db:
            favorite = await db.scalar(
                select(FavoriteMovie).where(
                    FavoriteMovie.id == movie.id,
                    FavoriteMovie.user_id == active_user["user_id"],
                )
            )
        assert favorite is not None
