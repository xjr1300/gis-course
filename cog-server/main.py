import asyncio
from typing import Optional, Tuple

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles

app = FastAPI()


@app.get("/rgbnir_remote_cog.png")
async def make_image_remote_cog(scale_min: float, scale_max: float):
    with Reader("http://fileserver/rgbnir_cog.tif") as image:
        image_data = image.preview([1, 2, 3])
        image_data.rescale(((scale_min, scale_max),))
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")


@app.get("/rgbnir_remote_cog_part.png")
async def make_image_remote_cog_part(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    max_size: int = 256,
    scale_min: float = 0.0,
    scale_max: float = 2000.0,
):
    with Reader("http://fileserver/rgbnir_cog.tif") as image:
        image_data = image.part(
            bbox=(minx, miny, maxx, maxy),
            indexes=(1, 2, 3),
            dst_crs="EPSG:32654",
            max_size=max_size,
        )
        image_data.rescale(((scale_min, scale_max),))
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")


@app.get("/tiles/{z}/{x}/{y}.png")
async def make_image_remote_cog_tile(
    z: int,
    x: int,
    y: int,
    scale_min: float = 0.0,
    scale_max: float = 2000.0,
):
    with Reader("http://fileserver/rgbnir_cog.tif") as image:
        image_data = image.tile(
            x, y, z, indexes=(1, 2, 3), resampling_method="bilinear"
        )
        image_data.rescale(((scale_min, scale_max),))
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")


def get_tile(
    url: str,
    z: int,
    x: int,
    y: int,
    indexes: Optional[Tuple[int, ...]],
    scale_min: float,
    scale_max: float,
):
    with Reader(url) as image:
        if not image.tile_exists(x, y, z):
            return None
        image_data = image.tile(x, y, z, indexes=indexes, resampling_method="bilinear")
        image_data.rescale(((scale_min, scale_max),))
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return png


@app.get("/tiles_async/{z}/{x}/{y}.png")
async def make_image_remote_cog_tile_async(
    z: int, x: int, y: int, scale_min: float = 0.0, scale_max: float = 2000.0
):
    if z < 6:
        return Response(status_code=404)
    loop = asyncio.get_event_loop()
    png = await loop.run_in_executor(
        None,
        get_tile,
        "http://fileserver/rgbnir_cog.tif",
        z,
        x,
        y,
        (1, 2, 3),
        scale_min,
        scale_max,
    )
    return Response(png, media_type="image/png")


@app.get("/tiles/b02/{z}/{x}/{y}.png")
async def make_image_remote_b2_tile_async(
    z: int, x: int, y: int, scale_min: float = 0.0, scale_max: float = 2000.0
):
    if z < 6:
        return Response(status_code=404)
    loop = asyncio.get_event_loop()
    png = await loop.run_in_executor(
        None,
        get_tile,
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/54/T/WN/2023/11/S2B_54TWN_20231118_1_L2A/B02.tif",
        z,
        x,
        y,
        None,
        scale_min,
        scale_max,
    )
    return Response(png, media_type="image/png")


app.mount("/", StaticFiles(directory="static"), name="static")