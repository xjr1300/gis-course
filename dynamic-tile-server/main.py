import psycopg2.pool
from fastapi import Depends, FastAPI, Response
from fastapi.staticfiles import StaticFiles

app = FastAPI()


# dsn=postgres://username:password@hostname:port/database?option...
pool = psycopg2.pool.SimpleConnectionPool(
    dsn="postgresql://postgres:postgres@postgis:5432/postgres", minconn=2, maxconn=4
)


def get_connection():
    try:
        conn = pool.getconn()
        yield conn
    finally:
        pool.putconn(conn)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/vector/{z}/{x}/{y}.pbf")
def get_tile(z: int, x: int, y: int, conn=Depends(get_connection)):
    sql = """
        WITH geometries AS (
            SELECT ST_AsMVTGeom(ST_Transform(geom, 3857), ST_TileEnvelope(%(z)s, %(x)s, %(y)s))
            FROM school
            WHERE ST_Transform(geom, 3857) && ST_TileEnvelope(%(z)s, %(x)s, %(y)s)
        )
        SELECT ST_AsMVT(geometries.*, 'vector')
        FROM geometries
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"z": z, "x": x, "y": y})
        geometries = cur.fetchone()[0]
    return Response(
        content=geometries.tobytes(), media_type="application/vnd.mapbox-vector-tile"
    )


@app.get("/admin/{z}/{x}/{y}.pbf")
def get_admin_tile(z: int, x: int, y: int, conn=Depends(get_connection)):
    sql = """
        WITH geometries AS (
            SELECT ST_AsMVTGeom(ST_Transform(geom, 3857), ST_TileEnvelope(%(z)s, %(x)s, %(y)s))
            FROM admin
            WHERE ST_Transform(geom, 3857) && ST_TileEnvelope(%(z)s, %(x)s, %(y)s)
        )
        SELECT ST_AsMVT(geometries.*, 'vector')
        FROM geometries
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"z": z, "x": x, "y": y})
        geometries = cur.fetchone()[0]
    return Response(
        content=geometries.tobytes(), media_type="application/vnd.mapbox-vector-tile"
    )


app.mount("/", StaticFiles(directory="static"), name="static")
