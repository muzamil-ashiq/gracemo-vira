/* GraceEMO — LPU Digital Twin 3D Campus Simulation Engine (Three.js) */

import * as THREE from 'three';

function rosToThree(x, y, z) {
  return { x: x, y: z, z: -y };
}

window.GraceGazebo = (function () {
  const canvas = document.getElementById('gazeboCanvas');
  if (!canvas) {
    return { setRobot() {}, setObstacles() {}, setScan() {}, setBuildings() {}, setDynamicAgents() {}, setWeather() {}, setDebugGrid() {}, lookAtRos() {}, zoom() {}, resetView() {} };
  }

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xb8d4ea);
  scene.fog = new THREE.FogExp2(0xb8d4ea, 0.0035);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 500);
  let az = 0.55;
  let el = 0.55;
  let dist = 18;
  let lookTarget = new THREE.Vector3(0, 0.7, 0);

  // Lighting
  const ambient = new THREE.AmbientLight(0xffffff, 0.85);
  scene.add(ambient);

  const hemi = new THREE.HemisphereLight(0xe8f4ff, 0x6b8f6a, 0.7);
  scene.add(hemi);

  const sun = new THREE.DirectionalLight(0xfff4d6, 1.15);
  sun.position.set(60, 100, 80);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 300;
  sun.shadow.camera.left = -120;
  sun.shadow.camera.right = 120;
  sun.shadow.camera.top = 120;
  sun.shadow.camera.bottom = -120;
  scene.add(sun);

  const fillLight = new THREE.DirectionalLight(0xffffff, 0.25);
  fillLight.position.set(-60, 40, -60);
  scene.add(fillLight);

  function makeCanvasTexture(draw, w, h) {
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    draw(c.getContext('2d'), w, h);
    const t = new THREE.CanvasTexture(c);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }
  function brickMap(grout, brick) {
    return makeCanvasTexture((ctx, w, h) => {
      ctx.fillStyle = grout; ctx.fillRect(0, 0, w, h);
      const bw = 28, bh = 12;
      for (let y = 0; y < h; y += bh) {
        const off = ((y / bh) % 2) * (bw / 2);
        for (let x = -bw; x < w + bw; x += bw) {
          ctx.fillStyle = brick;
          ctx.fillRect(x + off + 1, y + 1, bw - 2, bh - 2);
        }
      }
    }, 256, 128);
  }
  function makeNameSprite(text) {
    const c = document.createElement('canvas');
    c.width = 768; c.height = 128;
    const ctx = c.getContext('2d');
    ctx.fillStyle = 'rgba(255,255,255,0.95)';
    const r = 22;
    ctx.beginPath();
    ctx.moveTo(r, 16);
    ctx.arcTo(c.width - 16, 16, c.width - 16, c.height - 16, r);
    ctx.arcTo(c.width - 16, c.height - 16, 16, c.height - 16, r);
    ctx.arcTo(16, c.height - 16, 16, 16, r);
    ctx.arcTo(16, 16, c.width - 16, 16, r);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = '#ea580c'; ctx.lineWidth = 4; ctx.stroke();
    ctx.fillStyle = '#9a3412';
    ctx.font = 'bold 42px Inter, system-ui, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, c.width / 2, c.height / 2 + 2);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
    const sc = Math.min(26, Math.max(11, text.length * 0.72));
    spr.scale.set(sc, sc * (128 / 768), 1);
    spr.renderOrder = 30;
    spr.center.set(0.5, 0);
    return spr;
  }

  const grassTex = makeCanvasTexture((ctx, w, h) => {
    ctx.fillStyle = '#6f9a5c'; ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 2200; i++) {
      ctx.fillStyle = i % 3 ? '#7eab68' : '#5d8a4e';
      ctx.fillRect((i * 17) % w, (i * 29) % h, 3, 3);
    }
  }, 256, 256);
  grassTex.repeat.set(48, 48);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(240, 240), new THREE.MeshStandardMaterial({ map: grassTex, roughness: 0.96 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  const grid = new THREE.GridHelper(200, 40, 0xd7e4c8, 0x8faf7a);
  grid.position.y = 0.02;
  grid.visible = true;
  scene.add(grid);

  const asphaltTex = makeCanvasTexture((ctx, w, h) => {
    ctx.fillStyle = '#555a61'; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#e6dc9a'; ctx.fillRect(w / 2 - 2, 0, 4, h);
  }, 32, 128);
  asphaltTex.repeat.set(1, 20);
  const roadMat = new THREE.MeshStandardMaterial({ map: asphaltTex, roughness: 0.92 });
  const mainRoad = new THREE.Mesh(new THREE.PlaneGeometry(9, 200), roadMat);
  mainRoad.rotation.x = -Math.PI / 2; mainRoad.position.y = 0.04; scene.add(mainRoad);
  const crossRoad = new THREE.Mesh(new THREE.PlaneGeometry(200, 9), roadMat);
  crossRoad.rotation.x = -Math.PI / 2; crossRoad.position.set(0, 0.04, -20); scene.add(crossRoad);

  const walkMat = new THREE.MeshStandardMaterial({ color: 0xc2b8a6, roughness: 0.9 });
  [[-30, 5, 4, 90], [30, 5, 4, 90]].forEach(([x, y, sx, sy]) => {
    const wlk = new THREE.Mesh(new THREE.PlaneGeometry(sx, sy), walkMat);
    wlk.rotation.x = -Math.PI / 2;
    const p = rosToThree(x, y, 0.05);
    wlk.position.set(p.x, 0.05, p.z);
    scene.add(wlk);
  });

  const wallMat = new THREE.MeshStandardMaterial({ color: 0xcfc3b0, roughness: 0.75 });
  function addWall(cx, cy, sx, sy, h) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(sx, h, sy), wallMat);
    const p = rosToThree(cx, cy, h / 2);
    mesh.position.set(p.x, p.y, p.z); mesh.castShadow = true; scene.add(mesh);
  }
  addWall(0, 100, 202, 0.8, 2.4); addWall(0, -100, 202, 0.8, 2.4);
  addWall(100, 0, 0.8, 200, 2.4); addWall(-100, 0, 0.8, 200, 2.4);

  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x6b4a2b, roughness: 0.9 });
  const leafA = new THREE.MeshStandardMaterial({ color: 0x3a7a36, roughness: 0.82 });
  const leafB = new THREE.MeshStandardMaterial({ color: 0x2d6b32, roughness: 0.82 });
  function addTree(x, y, s) {
    const g = new THREE.Group();
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * s, 0.22 * s, 1.6 * s, 7), trunkMat);
    trunk.position.y = 0.8 * s;
    const leaf = new THREE.Mesh(new THREE.SphereGeometry(1.05 * s, 9, 7), Math.random() > 0.5 ? leafA : leafB);
    leaf.position.y = 2.15 * s; leaf.castShadow = true;
    g.add(trunk, leaf);
    const p = rosToThree(x, y, 0); g.position.set(p.x, 0, p.z); scene.add(g);
  }
  [[-18,-55],[18,-55],[-22,-78],[22,-78],[-55,8],[55,8],[-12,35],[14,32],[-78,20],[78,18],[-8,-88],[10,-88],[-60,-55],[60,-55],[-28,78],[28,78],[8,-12],[-8,8],[-70,-70],[70,-70],[-50,80],[50,82],[-25,-25],[25,8],[-55,-15],[58,-12],[-15,72],[16,78],[-85,-50],[85,40]].forEach(([tx, ty], i) => addTree(tx, ty, 0.9 + (i % 5) * 0.1));

  const lampMat = new THREE.MeshStandardMaterial({ color: 0x3a3f46, metalness: 0.45, roughness: 0.4 });
  const lampGlow = new THREE.MeshStandardMaterial({ color: 0xfff4cc, emissive: 0xffe08a, emissiveIntensity: 0.55 });
  function addLamp(x, y) {
    const g = new THREE.Group();
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 4.0, 6), lampMat);
    pole.position.y = 2.0; g.add(pole);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 8, 8), lampGlow);
    head.position.y = 4.1; g.add(head);
    const p = rosToThree(x, y, 0); g.position.set(p.x, 0, p.z); scene.add(g);
  }
  [[0,-40],[0,10],[0,40],[-20,-20],[20,-20],[-20,50],[20,50],[0,-70],[-8,-8],[8,-8],[-45,0],[45,0]].forEach(([x, y]) => addLamp(x, y));

  const benchMat = new THREE.MeshStandardMaterial({ color: 0x5a4634, roughness: 0.7 });
  function addBench(x, y, yaw) {
    const g = new THREE.Group();
    const seat = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.12, 0.45), benchMat);
    seat.position.y = 0.45; g.add(seat);
    const back = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.45, 0.08), benchMat);
    back.position.set(0, 0.72, -0.18); g.add(back);
    const p = rosToThree(x, y, 0); g.position.set(p.x, 0, p.z); g.rotation.y = yaw; scene.add(g);
  }
  [[-8, 6, 0], [8, 6, 0], [-12, -8, 1.57], [12, -8, -1.57], [-6, 48, 0], [8, 48, 0]].forEach(([x, y, yaw]) => addBench(x, y, yaw));

  const zebra = makeCanvasTexture((ctx, w, h) => {
    ctx.fillStyle = '#555a61'; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#f4f1e6';
    for (let i = 0; i < 8; i++) ctx.fillRect(0, i * 16, w, 8);
  }, 32, 128);
  const zebraMesh = new THREE.Mesh(new THREE.PlaneGeometry(8, 6), new THREE.MeshStandardMaterial({ map: zebra, roughness: 0.9 }));
  zebraMesh.rotation.x = -Math.PI / 2;
  zebraMesh.position.set(0, 0.05, 0);
  scene.add(zebraMesh);

  const parkMat = new THREE.MeshStandardMaterial({ color: 0x4a5058, roughness: 0.95 });
  const parking = new THREE.Mesh(new THREE.PlaneGeometry(22, 14), parkMat);
  parking.rotation.x = -Math.PI / 2;
  const pp = rosToThree(18, -8, 0.05);
  parking.position.set(pp.x, 0.045, pp.z);
  scene.add(parking);

  const chargePad = new THREE.Mesh(new THREE.CylinderGeometry(1.4, 1.4, 0.08, 24), new THREE.MeshStandardMaterial({ color: 0x1e3a5f, emissive: 0x2563eb, emissiveIntensity: 0.25 }));
  const cp = rosToThree(0, -8, 0.06);
  chargePad.position.set(cp.x, 0.08, cp.z);
  scene.add(chargePad);

  const gateMat = new THREE.MeshStandardMaterial({ color: 0x2c3340, metalness: 0.4, roughness: 0.45 });
  function addGate(x, y) {
    const g = new THREE.Group();
    [-2.4, 2.4].forEach((sx) => {
      const post = new THREE.Mesh(new THREE.BoxGeometry(0.35, 3.2, 0.35), gateMat);
      post.position.set(sx, 1.6, 0); g.add(post);
    });
    const bar = new THREE.Mesh(new THREE.BoxGeometry(5.2, 0.18, 0.18), new THREE.MeshStandardMaterial({ color: 0xf59e0b }));
    bar.position.y = 2.4; g.add(bar);
    const p = rosToThree(x, y, 0); g.position.set(p.x, 0, p.z); scene.add(g);
  }
  addGate(0, -96);

  const field = new THREE.Mesh(new THREE.PlaneGeometry(58, 38), new THREE.MeshStandardMaterial({ color: 0x4f8f45, roughness: 0.95 }));
  field.rotation.x = -Math.PI / 2;
  const fp = rosToThree(0, -70, 0.06);
  field.position.set(fp.x, 0.06, fp.z);
  scene.add(field);

  const buildingsGroup = new THREE.Group();
  scene.add(buildingsGroup);
  const facadeMaps = {
    academic: brickMap('#b37a52', '#c9926a'),
    academic_library: brickMap('#c4a06a', '#d6b888'),
    academic_research: brickMap('#a88870', '#bba088'),
    academic_labs: brickMap('#9a7a62', '#b09078'),
    commercial: brickMap('#c8b49c', '#d8c8b4'),
    commercial_social: brickMap('#c0a888', '#d2bea0'),
    healthcare: brickMap('#c8d4de', '#dde6ee'),
    residential: brickMap('#8aaa84', '#a3c09c'),
    sports: brickMap('#4f8a45', '#5c9a51')
  };
  const roofMat = new THREE.MeshStandardMaterial({ color: 0x5a6570, roughness: 0.55, metalness: 0.15 });
  const plinthMat = new THREE.MeshStandardMaterial({ color: 0x8a8680, roughness: 0.85 });
  const glassMat = new THREE.MeshStandardMaterial({ color: 0x7ec8e8, emissive: 0x163044, roughness: 0.2, metalness: 0.3, transparent: true, opacity: 0.92 });
  const doorMat = new THREE.MeshStandardMaterial({ color: 0x4a3728, roughness: 0.6 });

  const DEFAULT_BUILDINGS = [
    { id: 'b34', name: 'Block 34', type: 'academic', x: -40, y: -40, l: 40, w: 20, h: 12 },
    { id: 'b35', name: 'Block 35', type: 'academic', x: -40, y: -10, l: 35, w: 18, h: 12 },
    { id: 'b36', name: 'Block 36', type: 'academic', x: -40, y: 20, l: 38, w: 20, h: 15 },
    { id: 'b37', name: 'Block 37 — Central Library', type: 'academic_library', x: -40, y: 50, l: 45, w: 22, h: 15 },
    { id: 'b38', name: 'Block 38', type: 'academic', x: 40, y: -40, l: 36, w: 18, h: 12 },
    { id: 'b39', name: 'Block 39', type: 'academic_research', x: 40, y: -10, l: 32, w: 16, h: 9 },
    { id: 'b40', name: 'Block 40', type: 'academic', x: 40, y: 20, l: 34, w: 18, h: 12 },
    { id: 'b41', name: 'Block 41', type: 'academic_labs', x: 40, y: 50, l: 30, w: 16, h: 9 },
    { id: 'mall', name: 'Uni-Mall', type: 'commercial', x: 0, y: 60, l: 50, w: 25, h: 10 },
    { id: 'polis', name: 'Uni-Polis', type: 'commercial_social', x: 70, y: 60, l: 30, w: 20, h: 8 },
    { id: 'hospital', name: 'Uni-Hospital', type: 'healthcare', x: -70, y: 60, l: 35, w: 25, h: 12 },
    { id: 'bh1', name: 'Boys Hostel', type: 'residential', x: -75, y: -30, l: 20, w: 30, h: 15 },
    { id: 'gh1', name: 'Girls Hostel', type: 'residential', x: 75, y: -30, l: 20, w: 30, h: 15 }
  ];

  function addWindowGrid(group, bl, bh, bw) {
    const colsL = Math.max(4, Math.floor(bl / 4.2));
    const colsW = Math.max(3, Math.floor(bw / 4.2));
    const rows = Math.max(2, Math.floor(bh / 3.1));
    const faces = [
      { n: colsL, ax: 'x', z: bw / 2 + 0.06 },
      { n: colsL, ax: 'x', z: -bw / 2 - 0.06 },
      { n: colsW, ax: 'z', x: bl / 2 + 0.06 },
      { n: colsW, ax: 'z', x: -bl / 2 - 0.06 }
    ];
    faces.forEach((f) => {
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < f.n; c++) {
          const pane = new THREE.Mesh(new THREE.BoxGeometry(1.15, 1.25, 0.06), glassMat);
          const yy = -bh / 2 + 2.2 + r * (bh / (rows + 0.4));
          if (f.ax === 'x') pane.position.set(-bl / 2 + (c + 0.55) * (bl / f.n), yy, f.z);
          else {
            pane.position.set(f.x, yy, -bw / 2 + (c + 0.55) * (bw / f.n));
            pane.rotation.y = Math.PI / 2;
          }
          group.add(pane);
        }
      }
    });
  }

  function buildFacade(b) {
    const bx = b.position ? b.position.x : b.x;
    const by = b.position ? b.position.y : b.y;
    const bl = b.dimensions ? b.dimensions.length : b.l;
    const bw = b.dimensions ? b.dimensions.width : b.w;
    const bh = b.dimensions ? b.dimensions.height : b.h;
    const name = b.name || b.id || 'Building';
    const type = b.type || 'academic';
    const group = new THREE.Group();
    const bodyMat = new THREE.MeshStandardMaterial({ map: facadeMaps[type] || facadeMaps.academic, roughness: 0.72 });
    const body = new THREE.Mesh(new THREE.BoxGeometry(bl, bh, bw), bodyMat);
    body.position.y = bh / 2 + 0.25; body.castShadow = true; body.receiveShadow = true; group.add(body);
    const plinth = new THREE.Mesh(new THREE.BoxGeometry(bl + 0.8, 0.5, bw + 0.8), plinthMat);
    plinth.position.y = 0.25; group.add(plinth);
    const roof = new THREE.Mesh(new THREE.BoxGeometry(bl + 0.6, 0.45, bw + 0.6), roofMat);
    roof.position.y = bh + 0.48; group.add(roof);
    addWindowGrid(body, bl, bh, bw);
    const door = new THREE.Mesh(new THREE.BoxGeometry(2.2, 3.0, 0.2), doorMat);
    door.position.set(0, 1.7, bw / 2 + 0.12); group.add(door);
    const canopy = new THREE.Mesh(new THREE.BoxGeometry(4.2, 0.18, 1.6), roofMat);
    canopy.position.set(0, 3.3, bw / 2 + 0.7); group.add(canopy);
    const label = makeNameSprite(name);
    label.position.set(0, bh + 2.4, 0); group.add(label);
    const p = rosToThree(bx, by, 0);
    group.position.set(p.x, 0, p.z);
    return group;
  }

  function renderBuildings(list) {
    while (buildingsGroup.children.length > 0) buildingsGroup.remove(buildingsGroup.children[0]);
    const items = list && list.length ? list : DEFAULT_BUILDINGS;
    for (const b of items) {
      const bh = b.dimensions ? b.dimensions.height : b.h;
      if (bh !== undefined && bh < 1) continue;
      buildingsGroup.add(buildFacade(b));
    }
  }
  renderBuildings(DEFAULT_BUILDINGS);

  // Dynamic Agents (Pedestrians & Vehicles)
  const agentsGroup = new THREE.Group();
  scene.add(agentsGroup);
  const agentMeshes = {};

  const pedBody = new THREE.CapsuleGeometry(0.22, 0.9, 4, 8);
  const pedHead = new THREE.SphereGeometry(0.18, 10, 8);
  const vehGeo = new THREE.BoxGeometry(2.0, 1.2, 4.2);

  function makePedestrian(color) {
    const g = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.55 });
    const body = new THREE.Mesh(pedBody, mat);
    body.position.y = 0.85;
    const head = new THREE.Mesh(pedHead, mat);
    head.position.y = 1.55;
    g.add(body, head);
    g.castShadow = true;
    return g;
  }

  function updateDynamicAgents(agents) {
    if (!agents) return;
    const seen = new Set();

    for (const a of agents) {
      seen.add(a.id);
      let m = agentMeshes[a.id];
      if (!m) {
        const isVeh = a.type === 'car' || a.type === 'bus' || a.type === 'motorcycle';
        const color = a.color ? new THREE.Color(a.color[0]/255, a.color[1]/255, a.color[2]/255) : new THREE.Color(0x2563eb);
        if (isVeh) {
          m = new THREE.Mesh(vehGeo, new THREE.MeshStandardMaterial({ color, roughness: 0.5 }));
          m.castShadow = true;
        } else {
          m = makePedestrian(color);
        }
        agentsGroup.add(m);
        agentMeshes[a.id] = m;
      }
      const isVeh = a.type === 'car' || a.type === 'bus';
      const p = rosToThree(a.x, a.y, isVeh ? 0.7 : 0);
      m.position.set(p.x, p.y, p.z);
      m.rotation.y = (a.heading || 0);
    }

    // Remove deleted agents
    for (const id in agentMeshes) {
      if (!seen.has(id)) {
        agentsGroup.remove(agentMeshes[id]);
        delete agentMeshes[id];
      }
    }
  }

  // GRACEEMO-01 twin (matches URDF / product reference; not Gazebo physics)
  const robotGroup = new THREE.Group();
  scene.add(robotGroup);
  const white = new THREE.MeshStandardMaterial({ color: 0xeceff2, roughness: 0.22, metalness: 0.08 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x0a0c0e, roughness: 0.32, metalness: 0.45 });
  const tyre = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.72, metalness: 0.05 });
  const cyan = new THREE.MeshStandardMaterial({ color: 0x14c4e8, roughness: 0.2, metalness: 0.15, emissive: 0x0aa0c8, emissiveIntensity: 0.85 });
  const faceMat = new THREE.MeshStandardMaterial({ color: 0x05080a, roughness: 0.15, metalness: 0.35 });
  const screenMat = new THREE.MeshStandardMaterial({
    color: 0x0b1418, roughness: 0.18, metalness: 0.2,
    map: makeCanvasTexture((ctx, w, h) => {
      ctx.fillStyle = '#071018';
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = '#7ee8ff';
      ctx.font = 'bold 28px sans-serif';
      ctx.fillText('SYSTEM STATUS', 24, 48);
      ctx.font = '20px sans-serif';
      const rows = ['Navigation', 'AI-Assistant', 'Sensors', 'Battery', 'Connectivity'];
      rows.forEach((row, i) => {
        ctx.fillStyle = '#c9d4dc';
        ctx.fillText(row, 28, 88 + i * 28);
        ctx.fillStyle = '#3ddc84';
        ctx.fillText('Online', w - 120, 88 + i * 28);
      });
    }, 256, 256),
  });
  screenMat.map.wrapS = THREE.ClampToEdgeWrapping;
  screenMat.map.wrapT = THREE.ClampToEdgeWrapping;

  function addBox(parent, geo, mat, x, y, z) {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(x, y, z);
    m.castShadow = true;
    parent.add(m);
    return m;
  }

  // Local +X = ROS forward (chest / face)
  addBox(robotGroup, new THREE.BoxGeometry(0.38, 0.16, 0.36), dark, 0, 0.14, 0);
  addBox(robotGroup, new THREE.BoxGeometry(0.36, 0.12, 0.32), white, 0, 0.28, 0);
  addBox(robotGroup, new THREE.BoxGeometry(0.34, 0.12, 0.30), dark, 0, 0.40, 0);
  addBox(robotGroup, new THREE.BoxGeometry(0.32, 0.08, 0.28), white, 0, 0.50, 0);
  addBox(robotGroup, new THREE.BoxGeometry(0.11, 0.22, 0.10), white, 0, 0.62, 0.10);
  addBox(robotGroup, new THREE.BoxGeometry(0.11, 0.22, 0.10), white, 0, 0.62, -0.10);
  addBox(robotGroup, new THREE.BoxGeometry(0.28, 0.08, 0.18), dark, 0, 0.76, 0);
  addBox(robotGroup, new THREE.BoxGeometry(0.36, 0.36, 0.22), white, 0, 0.96, 0);
  addBox(robotGroup, new THREE.BoxGeometry(0.012, 0.14, 0.20), screenMat, 0.118, 1.02, 0);
  addBox(robotGroup, new THREE.BoxGeometry(0.01, 0.03, 0.16), dark, 0.122, 0.90, 0);

  const wr = 0.12;
  const wheelMeshes = [];
  [[0.14, -0.21], [0.14, 0.21], [-0.14, -0.21], [-0.14, 0.21]].forEach(([x, z]) => {
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(wr, wr, 0.08, 22), tyre);
    wheel.rotation.x = Math.PI / 2;
    wheel.position.set(x, wr, z);
    wheel.castShadow = true;
    robotGroup.add(wheel);
    wheelMeshes.push(wheel);
  });
  const footprint = new THREE.Mesh(
    new THREE.RingGeometry(0.28, 0.32, 32),
    new THREE.MeshBasicMaterial({ color: 0x22c55e, transparent: true, opacity: 0.55, side: THREE.DoubleSide })
  );
  footprint.rotation.x = -Math.PI / 2;
  footprint.position.y = 0.03;
  robotGroup.add(footprint);
  const cgMarker = new THREE.Mesh(
    new THREE.SphereGeometry(0.04, 12, 10),
    new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xf59e0b, emissiveIntensity: 0.7 })
  );
  cgMarker.position.set(0, 0.62, 0);
  robotGroup.add(cgMarker);

  const neckGroup = new THREE.Group();
  neckGroup.position.set(0, 1.16, 0);
  robotGroup.add(neckGroup);
  addBox(neckGroup, new THREE.CylinderGeometry(0.05, 0.05, 0.09, 16), dark, 0, 0.045, 0);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.13, 24, 18), white);
  head.scale.set(1.0, 0.95, 0.82);
  head.position.y = 0.16;
  head.castShadow = true;
  neckGroup.add(head);
  addBox(neckGroup, new THREE.BoxGeometry(0.012, 0.14, 0.18), faceMat, 0.12, 0.16, 0);
  const eyeGeo = new THREE.SphereGeometry(0.028, 12, 10);
  const eyeL = new THREE.Mesh(eyeGeo, cyan);
  eyeL.position.set(0.128, 0.18, 0.045);
  const eyeR = eyeL.clone();
  eyeR.position.z = -0.045;
  neckGroup.add(eyeL, eyeR);
  const mouth = addBox(neckGroup, new THREE.BoxGeometry(0.006, 0.008, 0.07), cyan, 0.128, 0.10, 0);

  const leftArm = new THREE.Group();
  leftArm.position.set(0, 1.08, 0.22);
  robotGroup.add(leftArm);
  const rightArm = new THREE.Group();
  rightArm.position.set(0, 1.08, -0.22);
  robotGroup.add(rightArm);
  function buildArm(g) {
    addBox(g, new THREE.CylinderGeometry(0.048, 0.048, 0.085, 14), dark, 0, 0, 0);
    const upper = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.042, 0.22, 12), white);
    upper.position.y = -0.12;
    g.add(upper);
    addBox(g, new THREE.CylinderGeometry(0.042, 0.042, 0.07, 12), dark, 0, -0.24, 0);
    const fore = new THREE.Mesh(new THREE.CylinderGeometry(0.036, 0.036, 0.20, 12), white);
    fore.position.y = -0.36;
    g.add(fore);
    addBox(g, new THREE.BoxGeometry(0.075, 0.09, 0.055), white, 0, -0.50, 0);
  }
  buildArm(leftArm);
  buildArm(rightArm);

  // Point Cloud LiDAR visualization
  const scanPointsGeo = new THREE.BufferGeometry();
  const scanMat = new THREE.PointsMaterial({ color: 0x2563eb, size: 0.18, transparent: true, opacity: 0.85 });
  const scanPoints = new THREE.Points(scanPointsGeo, scanMat);
  scene.add(scanPoints);

  const trailPts = [];
  const trailGeo = new THREE.BufferGeometry();
  const trailLine = new THREE.Line(trailGeo, new THREE.LineBasicMaterial({ color: 0x3b82f6, transparent: true, opacity: 0.85 }));
  scene.add(trailLine);

  const pinEl = document.getElementById('robot-pin');
  const compassEl = document.getElementById('compass');
  let followRobot = true;

  // Orbit / pan
  let isDragging = false;
  let isPanning = false;
  let prevX = 0, prevY = 0;

  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  canvas.addEventListener('mousedown', (e) => {
    if (e.button === 2) isPanning = true;
    else isDragging = true;
    prevX = e.clientX;
    prevY = e.clientY;
  });
  window.addEventListener('mouseup', () => { isDragging = false; isPanning = false; });
  window.addEventListener('mousemove', (e) => {
    if (!isDragging && !isPanning) return;
    const dx = e.clientX - prevX;
    const dy = e.clientY - prevY;
    if (isPanning) {
      followRobot = false;
      const right = new THREE.Vector3();
      camera.getWorldDirection(right);
      right.cross(camera.up).normalize();
      const up = new THREE.Vector3(0, 1, 0);
      lookTarget.addScaledVector(right, -dx * 0.04);
      lookTarget.addScaledVector(up, dy * 0.04);
    } else if (isDragging) {
      az -= dx * 0.008;
      el = Math.max(0.1, Math.min(1.5, el + dy * 0.008));
    }
    prevX = e.clientX;
    prevY = e.clientY;
  });
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    dist = Math.max(5, Math.min(140, dist + e.deltaY * 0.05));
  }, { passive: false });
  canvas.addEventListener('dblclick', () => { followRobot = true; dist = 12; });
  if (pinEl) {
    pinEl.style.cursor = 'pointer';
    pinEl.title = 'Click to focus GRACEEMO-01';
    pinEl.addEventListener('click', () => { followRobot = true; dist = 10; });
  }

  function updateCamera() {
    const cx = lookTarget.x + dist * Math.sin(az) * Math.cos(el);
    const cy = lookTarget.y + dist * Math.sin(el);
    const cz = lookTarget.z + dist * Math.cos(az) * Math.cos(el);
    camera.position.set(cx, cy, cz);
    camera.lookAt(lookTarget);
  }

  function resize() {
    const w = canvas.clientWidth || 800;
    const h = canvas.clientHeight || 500;
    if (canvas.width !== w || canvas.height !== h) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
  }

  function updatePin() {
    if (!pinEl) return;
    const v = robotGroup.position.clone();
    v.y += 1.55;
    v.project(camera);
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    const sx = (v.x * 0.5 + 0.5) * w;
    const sy = (-v.y * 0.5 + 0.5) * h;
    if (v.z > 1) {
      pinEl.style.display = 'none';
      return;
    }
    pinEl.style.display = 'block';
    pinEl.style.left = sx + 'px';
    pinEl.style.top = sy + 'px';
  }

  function animate() {
    requestAnimationFrame(animate);
    resize();
    updateCamera();
    if (compassEl) compassEl.style.transform = `rotate(${az * 57.3}deg)`;
    updatePin();
    renderer.render(scene, camera);
  }
  animate();

  return {
    setRobot(r) {
      if (!r) return;
      const p = rosToThree(r.x || 0, r.y || 0, 0);
      robotGroup.position.set(p.x, p.y, p.z);
      robotGroup.rotation.y = (r.yaw || 0);
      neckGroup.rotation.y = (r.neck_yaw || 0);
      neckGroup.rotation.z = (r.neck_pitch || 0);
      leftArm.rotation.z = (r.left_hand || 0);
      rightArm.rotation.z = (r.right_hand || 0);
      const cg = r.cg || {};
      cgMarker.position.set(cg.x || 0.01, cg.z || 0.62, -(cg.y || 0));
      const spin = (r.linear_v || 0) * 2.4;
      wheelMeshes.forEach((w) => { w.rotation.z += spin; });

      const last = trailPts[trailPts.length - 1];
      if (!last || Math.hypot(p.x - last.x, p.z - last.z) > 0.35) {
        trailPts.push(new THREE.Vector3(p.x, 0.12, p.z));
        if (trailPts.length > 220) trailPts.shift();
        trailGeo.setFromPoints(trailPts);
      }

      if (followRobot) lookTarget.lerp(new THREE.Vector3(p.x, 0.7, p.z), 0.08);
    },
    lookAtRos(x, y, d) {
      followRobot = false;
      const p = rosToThree(x, y, 0);
      lookTarget.set(p.x, 0.5, p.z);
      if (d) dist = d;
    },
    zoom(delta) {
      dist = Math.max(5, Math.min(140, dist + delta));
    },
    resetView() {
      followRobot = true;
      dist = 12;
      az = 0.55;
      el = 0.55;
    },
    focusRobot() {
      followRobot = true;
      dist = 10;
    },
    setScan(ranges, r) {
      if (!ranges || !ranges.length || !r) return;
      const pos = [];
      const n = ranges.length;
      for (let i = 0; i < n; i++) {
        const d = ranges[i];
        if (d >= 28.0 || d < 0.2) continue;
        const ang = (r.yaw || 0) - Math.PI + (i * 2.0 * Math.PI / n);
        const gx = (r.x || 0) + d * Math.cos(ang);
        const gy = (r.y || 0) + d * Math.sin(ang);
        const p = rosToThree(gx, gy, 0.25);
        pos.push(p.x, p.y, p.z);
      }
      scanPointsGeo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    },
    setBuildings(list) {
      renderBuildings(list);
    },
    setDynamicAgents(agents) {
      updateDynamicAgents(agents);
    },
    setDebugGrid(on) {
      grid.visible = !!on;
    },
    setWeather(w) {
      if (w === 'night') {
        scene.background.setHex(0x1a2740);
        scene.fog.color.setHex(0x1a2740);
        ambient.color.setHex(0x8899bb);
        ambient.intensity = 0.45;
        sun.intensity = 0.2;
      } else if (w === 'rain' || w === 'fog') {
        scene.background.setHex(0xa8bcc8);
        scene.fog.color.setHex(0xa8bcc8);
        ambient.color.setHex(0xffffff);
        ambient.intensity = 0.75;
        sun.intensity = 0.4;
      } else {
        scene.background.setHex(0xb8d4ea);
        scene.fog.color.setHex(0xb8d4ea);
        ambient.color.setHex(0xffffff);
        ambient.intensity = 0.85;
        sun.intensity = 1.15;
      }
    }
  };
})();
