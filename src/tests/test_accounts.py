

async def test_register_user_success(client):
    response = await client.post("/register/", json={"email": "test@test.com", "password": "TestTest1!"})
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@test.com"
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data

async def test_register_user_with_existing_email(client):
    response = await client.post("/register/", json={"email": "test@test1.com", "password": "TestTest1!"})
    assert response.status_code == 201

    response = await client.post("/register/", json={"email": "test@test1.com", "password": "TestTest1!"})
    assert response.status_code == 409
    data = response.json()
    assert data["detail"] == "A user with this email test@test1.com already exists."


async def test_register_user_with_invalid_password(client):
    response = await client.post("/register/", json={"email": "test@test1.com", "password": "testest!"})
    assert response.status_code == 422
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "password"]
    assert "uppercase letter" in data["detail"][0]["msg"]





