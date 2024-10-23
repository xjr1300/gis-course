import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.pool
from fastapi import Depends, FastAPI, Response
from fastapi.staticfiles import StaticFiles

from .model import PoiCreate, PoiUpdate

# from psycopg2._psycopg import _Cursor


@dataclass
class Poi:
    id: int
    name: str
    longitude: float
    latitude: float

    def geojson(self) -> Dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude],
            },
            "properties": {"id": self.id, "name": self.name},
        }


app = FastAPI()

pool = psycopg2.pool.SimpleConnectionPool(
    dsn="postgres://postgres:postgres@postgis:5432/postgres", minconn=2, maxconn=4
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


@app.get("/pois")
def get_pois(conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    id, name, ST_X(geom) longitude, ST_Y(geom) latitude
                FROM
                    poi
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
                "name": name,
            },
        }
        for id, name, longitude, latitude in results
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
    }


@app.get("/pois_sql")
def get_pois_sql(conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT ST_AsGeoJSON(poi.*) FROM poi")
        results = cur.fetchall()
    features = [json.loads(row[0]) for row in results]
    return {
        "type": "FeatureCollection",
        "features": features,
    }


@app.get("/pois_sql2")
def get_pois_sql2(bbox: str, conn=Depends(get_connection)):
    _bbox = bbox.split(",")
    if len(_bbox) != 4:
        raise ValueError(
            "bboxの値が不正です。minx,miny,maxx,maxyの順で指定してください。"
        )
    minx, miny, maxx, maxy = list(map(float, _bbox))
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                json_build_object(
                    'type', 'FeatureCollection',
                    'features', COALESCE(json_agg(ST_AsGeoJSON(poi.*)::json), '[]'::json)
                )
            FROM
                poi
            WHERE
                geom
                && ST_MakeEnvelope(%(minx)s, %(miny)s, %(maxx)s, %(maxy)s, 4326)
            LIMIT 1000
            """,
            {
                "minx": minx,
                "miny": miny,
                "maxx": maxx,
                "maxy": maxy,
            },
        )
        results = cur.fetchall()
        return results[0][0]


def retrieve_poi(cur: Any, id: int) -> Optional[Poi]:
    cur.execute(
        """
            SELECT
                id,
                name,
                ST_X(geom) longitude,
                ST_Y(geom) latitude
            FROM
                poi
            WHERE
                id = %s
            """,
        (id,),
    )
    values = cur.fetchone()
    if values is None:
        return None
    id, name, longitude, latitude = values
    return Poi(id, name, longitude, latitude)


@app.get("/pois/{id}")
def get_poi(id: int, conn=Depends(get_connection)):
    print(f"id: {id}")
    with conn.cursor() as cur:
        poi = retrieve_poi(cur, id)
    if poi is None:
        return Response(status_code=404)
    return poi.geojson()


@app.post("/pois")
def create_poi(data: PoiCreate, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO poi (name, geom)
            VALUES(%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            """,
            (data.name, data.longitude, data.latitude),
        )
        conn.commit()
        cur.execute("SELECT lastval()")
        result = cur.fetchone()
        poi = retrieve_poi(cur, result[0])
    assert poi is not None
    return poi.geojson()


@app.delete("/pois/{id}")
def delete_poi(id: int, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM poi WHERE id = %s", (id,))
        conn.commit()
    return Response(status_code=204)


@app.patch("/pois/{id}")
def update_poi(id: int, data: PoiUpdate, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM poi WHERE id = %s", (id,))
        if not cur.fetchone():
            return Response(status_code=404)

        cur.execute(
            """
            UPDATE poi
            SET
                name = COALESCE(%s, name),
                geom = ST_SetSRID(ST_MakePoint(COALESCE(%s, ST_X(geom)), COALESCE(%s, ST_Y(geom))), 4326)
            WHERE
                id = %s
            """,
            (data.name, data.longitude, data.latitude, id),
        )
        conn.commit()
        poi = retrieve_poi(cur, id)
        assert poi is not None
        return poi.geojson()


@app.get("/pois/tiles/{z}/{x}/{y}.pbf")
def get_pois_tiles(z: int, x: int, y: int, conn=Depends(get_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH mvtgeom AS (
                SELECT
                    ST_AsMVTGeom(
                        ST_Transform(geom, 3857),
                        ST_TileEnvelope(%(z)s, %(x)s, %(y)s)
                    ) geom,
                    id,
                    name
                FROM
                    poi
                WHERE
                    ST_Transform(geom, 3857)
                    && ST_TileEnvelope(%(z)s, %(x)s, %(y)s)
            )
            SELECT
                ST_AsMVT(mvtgeom.*, 'poi', 4096, 'geom')
            FROM
                mvtgeom
            """,
            {"z": z, "x": x, "y": y},
        )
        result = cur.fetchone()[0]
        return Response(
            content=result.tobytes(), media_type="application/vnd.mapbox-vector-tile"
        )


app.mount("/", StaticFiles(directory="static"), name="static")
