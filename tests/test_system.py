from unittest.mock import patch

from httpx import AsyncClient


async def test_liveness_probe(client: AsyncClient):
    response = await client.get("/system/live")

    assert response.status_code == 200
    assert response.json() == {"status": "pass"}
    assert (
        response.headers.get("cache-control") == "no-cache, no-store, must-revalidate"
    )


async def test_readiness_probe_success(client: AsyncClient):
    response = await client.get("/system/ready")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "pass"
    assert "database" in data["checks"]
    assert data["checks"]["database"]["status"] == "pass"
    assert (
        response.headers.get("cache-control") == "no-cache, no-store, must-revalidate"
    )


async def test_readiness_probe_db_failure(client: AsyncClient):
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
        mock_execute.side_effect = Exception("Connection refused")

        response = await client.get("/system/ready")

        assert response.status_code == 503
        data = response.json()

        assert data["status"] == "fail"
        assert data["checks"]["database"]["status"] == "fail"
        assert "Connection refused" in data["checks"]["database"]["detail"]


async def test_readiness_probe_db_timeout(client: AsyncClient):
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
        mock_execute.side_effect = TimeoutError("Query timed out")

        response = await client.get("/system/ready")

        assert response.status_code == 503
        data = response.json()

        assert data["status"] == "fail"
        assert data["checks"]["database"]["status"] == "fail"
        assert "Query timed out" in data["checks"]["database"]["detail"]
