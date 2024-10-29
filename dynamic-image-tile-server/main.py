from fastapi import FastAPI, Response
from rio_tiler.io import Reader
from rio_tiler.profiles import img_profiles

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/rgbnir.png")
async def make_image():
    with Reader("static/rgbnir.tif") as image:
        image_data = image.read([1, 2, 3])  # band1, 2, 3
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")


@app.get("/rgbnir_cog.png")
async def make_preview():
    with Reader("static/rgbnir_cog.tif") as image:
        image_data = image.preview([1, 2, 3])
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")


@app.get("/rbgnir_cog_rescale.png")
async def make_rescale():
    with Reader("static/rgbnir_cog.tif") as image:
        image_data = image.preview([1, 2, 3])
        image_data.rescale(((0, 3000),))
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")


@app.get("/rgbnir_cog_dynamic_rescale.png")
async def make_dynamic_rescale(scale_min: float, scale_max: float):
    with Reader("static/rgbnir_cog.tif") as image:
        image_data = image.preview([1, 2, 3])
        image_data.rescale(((scale_min, scale_max),))
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")


@app.get("/ndvi.png")
async def make_ndvi():
    with Reader("static/rgbnir_cog.tif") as image:
        image_data = image.preview(expression="(b4-b1)/(b4+b1)")
        image_data.rescale(((0, 1),))
    png = image_data.render(img_format="PNG", **img_profiles.get("png"))
    return Response(png, media_type="image/png")
