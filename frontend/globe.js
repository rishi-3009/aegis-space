import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";
import { makeEarthMaterial, geoToScene } from "./earth.js";

// Three.js scene: 1 unit = 1000 km
const KM_PER_UNIT = 1000;
const EARTH_RADIUS = 6.371;

// Map an ECI point [x, y, z] in km to a Three.js position in units
function eciToScene(x, y, z, target) {
  return target.set(x / KM_PER_UNIT, z / KM_PER_UNIT, -y / KM_PER_UNIT);
}

const LABEL_FONT = "bold 36px sans-serif";
const LABEL_PX_PER_UNIT = 160;

// Label is as wide as its text, so long object names are not cut off
function makeLabel(text) {
  const measure = document.createElement("canvas").getContext("2d");
  measure.font = LABEL_FONT;
  const width = Math.ceil(measure.measureText(text).width) + 16;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  ctx.font = LABEL_FONT;
  ctx.fillStyle = "#cfefff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, width / 2, 32);
  const material = new THREE.SpriteMaterial({
    map: new THREE.CanvasTexture(canvas),
    depthTest: false,
    transparent: true,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(width / LABEL_PX_PER_UNIT, 64 / LABEL_PX_PER_UNIT, 1);
  sprite.position.set(0, 0.45, 0);
  return sprite;
}

export function createGlobe(container) {
  // Transparent canvas, so the panel's blue gradient shows behind the Earth
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
  camera.position.set(0, 10, 26);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  // Panning would slide the Earth out of view, so only rotate and zoom
  controls.enablePan = false;

  scene.add(new THREE.AmbientLight(0x404a5c));
  const sun = new THREE.DirectionalLight(0xffffff, 1.2);
  sun.position.set(10, 5, 10);
  scene.add(sun);

  // Real Earth at night with city lights, and a thin atmosphere rim
  const earth = new THREE.Mesh(
    new THREE.SphereGeometry(EARTH_RADIUS, 96, 64),
    makeEarthMaterial(renderer)
  );
  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(EARTH_RADIUS * 1.012, 64, 48),
    new THREE.MeshBasicMaterial({
      color: 0x6db4ff,
      side: THREE.BackSide,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  scene.add(earth, atmosphere);

  // Every object's full track, by id, so any object can be looked up later
  const tracks = new Map();
  // Debris and satellites are drawn as one THREE.Points per group, not one mesh each
  const groups = [];
  const primaries = new Map();
  const tmp = new THREE.Vector3();
  const tmpA = new THREE.Vector3();
  const tmpB = new THREE.Vector3();

  // Red line and threat zone for the selected conjunction
  const linkGeometry = new THREE.BufferGeometry();
  linkGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
  const link = new THREE.Line(linkGeometry, new THREE.LineBasicMaterial({ color: 0xff3b3b }));
  link.frustumCulled = false;
  link.visible = false;
  scene.add(link);

  const threat = new THREE.Mesh(
    new THREE.SphereGeometry(0.3, 24, 16),
    new THREE.MeshBasicMaterial({ color: 0xff3b3b, transparent: true, opacity: 0.25, depthWrite: false })
  );
  // Label goes below the zone so it does not sit on top of the primary's label
  const threatLabel = makeLabel("NOT TO SCALE");
  threatLabel.position.y = -0.45;
  threat.add(threatLabel);
  threat.visible = false;
  scene.add(threat);

  let focus = null;
  let currentF = 0;

  // Distance from the Earth's centre at which the whole sphere just fits the panel,
  // using the narrower of the two field-of-view axes
  function fitDistance() {
    const vfov = THREE.MathUtils.degToRad(camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
    return (EARTH_RADIUS * 1.12) / Math.sin(Math.min(vfov, hfov) / 2);
  }

  // Keep the whole Earth in view. The camera's distance is measured from the
  // orbit target, so the closest zoom is reduced by how far the target is from the centre.
  let fitted = false;
  function fitGlobe() {
    const fit = fitDistance();
    const offset = controls.target.length();
    controls.minDistance = Math.max(fit - offset, 1);
    controls.maxDistance = fit * 3;
    // Start looking at Europe and Africa with the whole Earth filling the panel,
    // then leave the user's zoom alone
    if (!fitted) {
      geoToScene(25, 25, fit * 1.05, camera.position);
      fitted = true;
    }
  }

  // Keep the red line and threat zone on the moving objects
  function updateFocus() {
    const primary = positionAt(tracks.get(focus.primaryId), currentF, tmpA);
    const secondary = positionAt(tracks.get(focus.secondaryId), currentF, tmpB);
    const pos = linkGeometry.attributes.position.array;
    pos[0] = primary.x;
    pos[1] = primary.y;
    pos[2] = primary.z;
    pos[3] = secondary.x;
    pos[4] = secondary.y;
    pos[5] = secondary.z;
    linkGeometry.attributes.position.needsUpdate = true;
    threat.position.copy(secondary);
  }

  // Position of a track at fractional step index f, in scene units
  function positionAt(track, f, target) {
    const i0 = Math.floor(f);
    const i1 = Math.min(i0 + 1, globe.steps - 1);
    const a = f - i0;
    const p0 = track[i0];
    const p1 = track[i1];
    return eciToScene(
      p0[0] + (p1[0] - p0[0]) * a,
      p0[1] + (p1[1] - p0[1]) * a,
      p0[2] + (p1[2] - p0[2]) * a,
      target
    );
  }

  function addGroup(list, color, size) {
    if (list.length === 0) return;
    const positions = new Float32Array(list.length * 3);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({ color, size, sizeAttenuation: true });
    const points = new THREE.Points(geometry, material);
    points.frustumCulled = false;
    scene.add(points);
    groups.push({ tracks: list, positions, geometry });
  }

  function addPrimary(info, track) {
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0x33e0ff })
    );
    mesh.add(makeLabel(info.name));
    scene.add(mesh);

    const orbitPoints = track.map((p) => eciToScene(p[0], p[1], p[2], new THREE.Vector3()));
    const orbit = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(orbitPoints),
      new THREE.LineBasicMaterial({ color: 0x33e0ff, transparent: true, opacity: 0.5 })
    );
    scene.add(orbit);

    primaries.set(info.id, { info, track, mesh });
  }

  const globe = {
    scene,
    camera,
    controls,
    renderer,
    steps: 0,
    stepSeconds: 60,
    startMs: 0,

    // Build the scene from /api/objects and /api/trajectories responses
    load(objectsResp, traj) {
      this.steps = traj.steps;
      this.stepSeconds = traj.step_seconds;
      this.startMs = Date.parse(traj.start);

      const meta = new Map(objectsResp.objects.map((o) => [o.id, o]));
      const debris = [];
      const satellites = [];

      for (const [id, track] of Object.entries(traj.objects)) {
        tracks.set(id, track);
        const info = meta.get(id) || { id, name: id, type: "debris", is_primary: false };
        if (info.is_primary) {
          addPrimary(info, track);
        } else if (info.type === "satellite") {
          satellites.push(track);
        } else {
          debris.push(track);
        }
      }

      addGroup(debris, 0x8a94a6, 0.035);
      addGroup(satellites, 0x33e0ff, 0.06);
      this.setTime(0);
    },

    // f is a fractional step index, e.g. 972.5
    setTime(f) {
      currentF = f;
      // Plain loops, not forEach, so nothing is allocated per frame
      for (const group of groups) {
        const count = group.tracks.length;
        for (let k = 0; k < count; k++) {
          positionAt(group.tracks[k], f, tmp);
          group.positions[k * 3] = tmp.x;
          group.positions[k * 3 + 1] = tmp.y;
          group.positions[k * 3 + 2] = tmp.z;
        }
        group.geometry.attributes.position.needsUpdate = true;
      }
      for (const { track, mesh } of primaries.values()) {
        mesh.position.copy(positionAt(track, f, tmp));
      }
      if (focus) updateFocus();
    },

    // Show the red line and threat zone, and move the camera to look at the primary
    focus(primaryId, secondaryId) {
      focus = { primaryId, secondaryId };
      link.visible = true;
      threat.visible = true;
      updateFocus();

      const target = positionAt(tracks.get(primaryId), currentF, new THREE.Vector3());
      controls.target.copy(target);
      // Camera sits outward from the primary, so the Earth still fills the view behind it
      const outward = target.clone().normalize();
      const distance = Math.max(fitDistance() * 1.05 - target.length(), 1);
      camera.position.copy(target).addScaledVector(outward, distance);
      fitGlobe();
    },

    clearFocus() {
      focus = null;
      link.visible = false;
      threat.visible = false;
    },

    // Scene position of any object at fractional step index f
    getPosition(id, f, target = new THREE.Vector3()) {
      return positionAt(tracks.get(id), f, target);
    },

    primaries,

    resize() {
      const w = container.clientWidth;
      const h = container.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      fitGlobe();
    },

    render() {
      controls.update();
      renderer.render(scene, camera);
    },
  };

  return globe;
}
