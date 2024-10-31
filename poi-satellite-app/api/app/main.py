#
# AWSが公開するSTAC Browser L2A Collectionに画像が存在するか確認するAPIの実行例
# curl https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items?limit=12&bbox=139,35,140,36
#

import httpx
import psycopg2
import psycopg2.pool
from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from rio_tiler.io import Reader

from .model import PointCreate, PointUpdate

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.198.151:5173",
    ],
    allow_methods=[
        "*",
    ],
)

pool = psycopg2.pool.SimpleConnectionPool(
    dsn="postgresql://postgres:postgres@postgis:5432/poi_satellite_app",
    minconn=2,
    maxconn=4,
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


# @app.get("/points")
# def get_points(bbox: str, conn=Depends(get_connection)):
#    _bbox = bbox.split(",")
#    if len(_bbox) != 4:
#        raise ValueError(
#            "bboxの値が不正です。minx,miny,maxx,maxyの順で指定してください。"
#        )
#    minx, miny, maxx, maxy = tuple(map(float, _bbox))
#    with conn.cursor() as cur:
#        cur.execute(
#            """
#            SELECT json_build_object(
#                'type', 'FeatureCollection',
#                'features', COALESCE(json_agg(ST_AsGeoJSON(points.*)::json), '[]'::json)
#            )
#            FROM points
#            WHERE geom && ST_MakeEnvelope(%(minx)s, %(minx)s, %(maxx)s, %(maxy)s, 4326)
#            LIMIT 1000
#            """,
#            {"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy},
#        )
#        geojson = cur.fetchone()
#        return geojson[0]


@app.get("/points")
def get_points(conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                ST_X(geom) longitude,
                ST_Y(geom) latitude
            FROM
                points
            """
        )
        results = cur.fetchall()
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [longitude, latitude],
            },
            "properties": {
                "id": id,
            },
        }
        for id, longitude, latitude in results
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def point_geojson(cur, id: int):
    cur.execute(
        """
        SELECT id, ST_X(geom) longitude, ST_Y(geom) latitude
        FROM points
        WHERE id = %s
        """,
        (id,),
    )
    id, longitude, latitude = cur.fetchone()

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude],
        },
        "properties": {
            "id": id,
        },
    }


@app.post("/points")
def create_point(data: PointCreate, conn=Depends(get_connection)):
    """
    curl -X POST -H "Content-Type: application/json" -d '{"longitude": 139.6923, "latitude": 35.68930}' http://localhost:3000/points
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO points (geom)
            VALUES (
                ST_SetSRID(
                    ST_MakePoint(%s, %s),
                    4326
                )
            )
            """,
            (data.longitude, data.latitude),
        )
        conn.commit()

        cur.execute("SELECT lastval()")
        result = cur.fetchone()
        _id = result[0]
        return point_geojson(cur, _id)


@app.patch("/points/{id}")
def update_point(id: int, data: PointUpdate, conn=Depends(get_connection)):
    """
    curl -X PATCH -H "Content-Type: application/json" -d '{"longitude": 139.0, "latitude": 35.0}' http://localhost:3000/points/1
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE points
            SET
                geom = ST_SetSRID(
                    ST_MakePoint(
                        COALESCE(%s, ST_X(geom)),
                        COALESCE(%s, ST_Y(geom))
                    ),
                    4326
                )
            WHERE id = %s
            """,
            (data.longitude, data.latitude, id),
        )
        conn.commit()
        return point_geojson(cur, id)


@app.delete("/points/{id}")
def delete_point(id: int, conn=Depends(get_connection)):
    """
    curl --include -X DELETE http://localhost:3000/points/1
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM points
            WHERE id = %s
            """,
            (id,),
        )
        conn.commit()
    return Response(status_code=204)


async def search_dataset(
    minx: float, miny: float, maxx: float, maxy: float, limit: int = 12
):
    url = "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items"
    params = {"limit": limit, "bbox": f"{minx},{miny},{maxx},{maxy}"}
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


@app.get("/points/{id}/satellite.jpg")
async def satellite_preview(
    id: int, max_size: int = 256, buffer: float = 0.01, conn=Depends(get_connection)
):
    print(f"id: {id}")
    if max_size > 1024:
        return Response(
            status_code=400, content="max_sizeは1024未満を指定してください。"
        )
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ST_X(geom) longitude,
                ST_Y(geom) latitude
            FROM
                points
            WHERE
                id = %s
            """,
            (id,),
        )
        result = cur.fetchone()
        if not result:
            return Response(status_code=404)
        longitude, latitude = result

    minx = longitude - buffer
    miny = latitude - buffer
    maxx = longitude + buffer
    maxy = latitude + buffer
    datasets = await search_dataset(minx, miny, maxx, maxy, limit=1)
    if len(datasets["features"]) == 0:
        return Response(status_code=404)
    feature = datasets["features"][0]
    cog_url = feature["assets"]["visual"]["href"]

    with Reader(cog_url) as src:
        image = src.preview(max_size=max_size)
    jpeg = image.render(img_format="JPEG")
    return Response(content=jpeg, media_type="image/jpeg")
