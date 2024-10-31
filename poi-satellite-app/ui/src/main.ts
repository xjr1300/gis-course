import "maplibre-gl/dist/maplibre-gl.css";
import { Map, Marker, Popup } from "maplibre-gl";
import { createPoint, deletePoint, loadPoints, satelliteImageUrl } from "./api";

const map = new Map({
  container: "app",
  maxZoom: 18,
  style: {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution: "@ OpenStreetMap contributors",
      },
    },
    layers: [
      {
        id: "osm",
        type: "raster",
        source: "osm",
      },
    ],
  },
  center: [139.767125, 35.681236],
});

const markers: Marker[] = [];
let isMarkerClicked = false;

const loadMarkers = async () => {
  const points = await loadPoints();
  points.features.forEach((feature) => {
    const popup = new Popup().setMaxWidth("500px");
    const marker = new Marker()
      .setLngLat(feature.geometry.coordinates)
      .addTo(map)
      .setPopup(popup);
    marker.getElement().addEventListener("click", () => {
      isMarkerClicked = true;
      popup.setDOMContent(createPopupDom(feature.properties.id));
    });
    markers.push(marker);
  });
};

const clearMarkers = () => {
  markers.forEach((marker) => marker.remove());
};

const createPopupDom = (id: string) => {
  const popupDom = document.createElement("div");
  popupDom.style.display = "flex";
  popupDom.style.flexDirection = "column";

  const anchor = document.createElement("a");
  anchor.href = satelliteImageUrl(id, 1024);
  anchor.innerHTML = `<img src="${satelliteImageUrl(
    id
  )}" width="256" height="256" />`;

  const buttonDom = document.createElement("button");
  buttonDom.textContent = "Delete";
  buttonDom.onclick = async () => {
    if (!confirm("Do you want to delete this point?")) {
      return;
    }
    await deletePoint(id);
    clearMarkers();
    await loadMarkers();
  };

  popupDom.appendChild(anchor);
  popupDom.appendChild(buttonDom);
  return popupDom;
};

map.on("load", async () => {
  await loadMarkers();
});

map.on("click", async (e) => {
  if (isMarkerClicked) {
    isMarkerClicked = false;
    return;
  }
  if (!confirm("Do you want to create a new point?")) {
    return;
  }
  const { lng, lat } = e.lngLat;
  await createPoint({ longitude: lng, latitude: lat });
  clearMarkers();
  await loadMarkers();
});
