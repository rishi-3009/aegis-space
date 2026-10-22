import * as THREE from "three";

// NASA surface and city-lights maps, stored in assets/ so the page works offline
const SURFACE_MAP = "./assets/earth_atmos_2048.jpg";
const LIGHTS_MAP = "./assets/earth_lights_2048.png";

function loadTexture(url, renderer) {
  const texture = new THREE.TextureLoader().load(url);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return texture;
}

// Night-side Earth: dim real surface colours, with city lights shining from the lights map
export function makeEarthMaterial(renderer) {
  return new THREE.MeshPhongMaterial({
    map: loadTexture(SURFACE_MAP, renderer),
    // Darkens the day-time surface so the planet reads as a night view
    color: 0x8590a6,
    emissiveMap: loadTexture(LIGHTS_MAP, renderer),
    emissive: 0xffa84d,
    emissiveIntensity: 1.6,
    shininess: 6,
    specular: 0x223044,
  });
}

// Point on the sphere for a lat/lon, using the same mapping as SphereGeometry and the textures
export function geoToScene(lat, lon, radius, target) {
  const la = (lat * Math.PI) / 180;
  const lo = (lon * Math.PI) / 180;
  return target.set(
    radius * Math.cos(la) * Math.cos(lo),
    radius * Math.sin(la),
    -radius * Math.cos(la) * Math.sin(lo)
  );
}
