import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface ThreeDroneOperationsSceneProps {
  onHoverStateChange?: (hovered: boolean) => void;
}

export const ThreeDroneOperationsScene: React.FC<ThreeDroneOperationsSceneProps> = () => {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // --- 1. Scene, Camera & WebGL Renderer ---
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x030712, 0.018);

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 560;

    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000);
    camera.position.set(0, 1.2, 13);
    camera.lookAt(1.8, 0.2, 0);

    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;
    container.appendChild(renderer.domElement);

    // --- 2. Lighting Rig ---
    // Ambient space light
    const ambientLight = new THREE.AmbientLight(0x0a1936, 2.0);
    scene.add(ambientLight);

    // Key sunlight highlighting metallic carbon chassis
    const sunLight = new THREE.DirectionalLight(0xe0f2fe, 4.0);
    sunLight.position.set(12, 16, 14);
    scene.add(sunLight);

    // Cyan rim/accent light
    const cyanRimLight = new THREE.DirectionalLight(0x00d9ff, 2.8);
    cyanRimLight.position.set(-10, -5, -4);
    scene.add(cyanRimLight);

    // --- 3. Earth Globe with Indian Operations (Procedural Map Texture) ---
    const createEarthTexture = (): THREE.CanvasTexture => {
      const cvs = document.createElement('canvas');
      cvs.width = 2048;
      cvs.height = 1024;
      const ctx = cvs.getContext('2d');
      if (!ctx) return new THREE.CanvasTexture(cvs);

      // Deep ocean gradient
      const oceanGrad = ctx.createLinearGradient(0, 0, 0, 1024);
      oceanGrad.addColorStop(0, '#020617');
      oceanGrad.addColorStop(0.3, '#040d21');
      oceanGrad.addColorStop(0.7, '#071536');
      oceanGrad.addColorStop(1, '#020617');
      ctx.fillStyle = oceanGrad;
      ctx.fillRect(0, 0, 2048, 1024);

      // Continental landmasses (stylized dark terrain with subtle topographic noise)
      ctx.fillStyle = '#0f2444';
      ctx.beginPath();
      // Indian Subcontinent (approx coords in 2048x1024 space)
      ctx.moveTo(1320, 360);
      ctx.lineTo(1360, 420);
      ctx.lineTo(1420, 470);
      ctx.lineTo(1380, 560);
      ctx.lineTo(1350, 620); // South tip (Kanyakumari)
      ctx.lineTo(1310, 540); // West coast (Mumbai/Goa)
      ctx.lineTo(1280, 460); // Gujarat
      ctx.lineTo(1290, 380);
      ctx.closePath();
      ctx.fill();

      // Eurasia block
      ctx.fillRect(900, 260, 750, 180);
      // Southeast Asia
      ctx.fillRect(1440, 480, 260, 180);
      // Middle East
      ctx.fillRect(1150, 380, 140, 160);

      // Grid coordinate latitude/longitude lines (faint cyan)
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
      ctx.lineWidth = 1;
      for (let y = 100; y < 1000; y += 120) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(2048, y);
        ctx.stroke();
      }
      for (let x = 100; x < 2048; x += 150) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, 1024);
        ctx.stroke();
      }

      // City light clusters (golden-amber & cyan nodes)
      const drawCityLight = (cx: number, cy: number, r: number, color: string) => {
        const radGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        radGrad.addColorStop(0, color);
        radGrad.addColorStop(0.4, 'rgba(251, 191, 36, 0.6)');
        radGrad.addColorStop(1, 'rgba(251, 191, 36, 0)');
        ctx.fillStyle = radGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();
      };

      // Indian Hubs: Mumbai, Delhi, Bengaluru, Hyderabad, Kolkata, Chennai
      drawCityLight(1315, 500, 24, '#ffffff'); // Mumbai (Intense)
      drawCityLight(1335, 410, 22, '#ffffff'); // Delhi/NCR
      drawCityLight(1340, 570, 20, '#ffffff'); // Bengaluru
      drawCityLight(1350, 530, 18, '#ffffff'); // Hyderabad
      drawCityLight(1410, 460, 18, '#ffffff'); // Kolkata
      drawCityLight(1360, 580, 16, '#ffffff'); // Chennai

      // Global corridor lights
      drawCityLight(1210, 420, 16, '#00d9ff'); // Dubai
      drawCityLight(1520, 580, 16, '#00d9ff'); // Singapore

      // Scattered night-side settlement clusters
      ctx.fillStyle = 'rgba(254, 240, 138, 0.7)';
      for (let i = 0; i < 160; i++) {
        const lx = 1290 + Math.random() * 140;
        const ly = 390 + Math.random() * 220;
        ctx.fillRect(lx, ly, Math.random() * 2 + 1, Math.random() * 2 + 1);
      }

      const tex = new THREE.CanvasTexture(cvs);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.ClampToEdgeWrapping;
      return tex;
    };

    const earthRadius = 14;
    const earthGeo = new THREE.SphereGeometry(earthRadius, 64, 64);
    const earthMat = new THREE.MeshStandardMaterial({
      map: createEarthTexture(),
      roughness: 0.75,
      metalness: 0.15,
      emissive: 0x05132d,
      emissiveIntensity: 0.35,
    });
    const earthMesh = new THREE.Mesh(earthGeo, earthMat);
    // Position the globe in the background right, tilted toward India
    earthMesh.position.set(9.5, -8.2, -13);
    earthMesh.rotation.set(0.35, -1.95, -0.15);
    scene.add(earthMesh);

    // Atmosphere Outer Cyan Rim Glow
    const atmosGeo = new THREE.SphereGeometry(earthRadius * 1.025, 64, 64);
    const atmosMat = new THREE.MeshBasicMaterial({
      color: 0x00d9ff,
      transparent: true,
      opacity: 0.22,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
    });
    const atmosMesh = new THREE.Mesh(atmosGeo, atmosMat);
    atmosMesh.position.copy(earthMesh.position);
    scene.add(atmosMesh);

    // --- 4. 3D Flight Trajectory Arcs Across Operations ---
    const arcGroup = new THREE.Group();
    earthMesh.add(arcGroup);

    // Convert lat/lon on sphere to Vector3
    const latLonToVector3 = (lat: number, lon: number, radius: number): THREE.Vector3 => {
      const phi = (90 - lat) * (Math.PI / 180);
      const theta = (lon + 180) * (Math.PI / 180);
      return new THREE.Vector3(
        -radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta)
      );
    };

    // Indian hub coordinates (approx latitude/longitude)
    const hubs = [
      { name: 'Mumbai', lat: 19.076, lon: 72.877 },
      { name: 'Delhi', lat: 28.613, lon: 77.209 },
      { name: 'Bengaluru', lat: 12.971, lon: 77.594 },
      { name: 'Hyderabad', lat: 17.385, lon: 78.486 },
      { name: 'Kolkata', lat: 22.572, lon: 88.363 },
      { name: 'Dubai', lat: 25.204, lon: 55.27 },
    ];

    const arcPairs = [
      [0, 1], [0, 2], [1, 3], [0, 3], [2, 3], [3, 4], [0, 5],
    ];

    const arcCurves: { curve: THREE.QuadraticBezierCurve3; pulseMesh: THREE.Mesh }[] = [];

    arcPairs.forEach(([i, j], pairIdx) => {
      const start = latLonToVector3(hubs[i].lat, hubs[i].lon, earthRadius + 0.05);
      const end = latLonToVector3(hubs[j].lat, hubs[j].lon, earthRadius + 0.05);

      // Midpoint pulled outward for curved high-altitude trajectory
      const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
      const midLen = mid.length();
      mid.normalize().multiplyScalar(midLen + 1.2 + (pairIdx % 3) * 0.4);

      const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
      const points = curve.getPoints(36);
      const arcGeo = new THREE.BufferGeometry().setFromPoints(points);

      const isPrimary = pairIdx === 0 || pairIdx === 1;
      const arcMat = new THREE.LineBasicMaterial({
        color: isPrimary ? 0x00d9ff : 0x38bdf8,
        transparent: true,
        opacity: isPrimary ? 0.85 : 0.45,
        blending: THREE.AdditiveBlending,
      });

      const line = new THREE.Line(arcGeo, arcMat);
      arcGroup.add(line);

      // Telemetry pulse packet travelling along the arc
      const pulseGeo = new THREE.SphereGeometry(0.09, 8, 8);
      const pulseMat = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        blending: THREE.AdditiveBlending,
      });
      const pulseMesh = new THREE.Mesh(pulseGeo, pulseMat);
      arcGroup.add(pulseMesh);

      arcCurves.push({ curve, pulseMesh });
    });

    // Glowing location beacon pins
    hubs.slice(0, 3).forEach((hub) => {
      const pos = latLonToVector3(hub.lat, hub.lon, earthRadius + 0.08);
      const pinGeo = new THREE.SphereGeometry(0.14, 12, 12);
      const pinMat = new THREE.MeshBasicMaterial({
        color: 0x00d9ff,
        blending: THREE.AdditiveBlending,
      });
      const pin = new THREE.Mesh(pinGeo, pinMat);
      pin.position.copy(pos);
      arcGroup.add(pin);
    });

    // --- 5. REAL PHYSICAL 3D QUADCOPTER UAV MODEL ---
    const drone = new THREE.Group();
    // Position drone in midground matching reference composition
    drone.position.set(3.4, 0.4, 2.0);
    // Angled 3/4 perspective
    drone.rotation.set(0.18, -0.42, 0.04);
    scene.add(drone);

    // Materials
    const carbonDarkMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.28,
      metalness: 0.88,
    });
    const carbonAccentMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.32,
      metalness: 0.75,
    });
    const titaniumMat = new THREE.MeshStandardMaterial({
      color: 0x475569,
      roughness: 0.22,
      metalness: 0.95,
    });
    const cyanLedMat = new THREE.MeshBasicMaterial({
      color: 0x00d9ff,
    });
    const opticalGlassMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      roughness: 0.08,
      metalness: 0.98,
      emissive: 0x0369a1,
      emissiveIntensity: 0.4,
    });
    const propBlurMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.26,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });

    // 5.1 Central Fuselage Body
    const fuselageGroup = new THREE.Group();
    drone.add(fuselageGroup);

    // Main center aerodynamic hull
    const mainBodyGeo = new THREE.BoxGeometry(1.6, 0.38, 2.2, 4, 2, 4);
    const mainBody = new THREE.Mesh(mainBodyGeo, carbonDarkMat);
    fuselageGroup.add(mainBody);

    // Sloped upper avionics & battery canopy
    const canopyGeo = new THREE.BoxGeometry(1.2, 0.28, 1.6);
    const canopy = new THREE.Mesh(canopyGeo, carbonAccentMat);
    canopy.position.set(0, 0.25, -0.1);
    fuselageGroup.add(canopy);

    // Top deck branding plate ("SKYLARK" carbon bar)
    const plateGeo = new THREE.BoxGeometry(0.85, 0.06, 0.7);
    const plate = new THREE.Mesh(plateGeo, carbonDarkMat);
    plate.position.set(0, 0.42, -0.1);
    fuselageGroup.add(plate);

    // Front nose optics & LiDAR bar (glowing electric cyan visor)
    const frontVisorGeo = new THREE.BoxGeometry(1.2, 0.12, 0.2);
    const frontVisor = new THREE.Mesh(frontVisorGeo, cyanLedMat);
    frontVisor.position.set(0, 0.08, 1.12);
    fuselageGroup.add(frontVisor);

    // Side LED light strips
    const sideLedLeftGeo = new THREE.BoxGeometry(0.06, 0.06, 1.8);
    const sideLedLeft = new THREE.Mesh(sideLedLeftGeo, cyanLedMat);
    sideLedLeft.position.set(-0.81, 0.05, 0);
    fuselageGroup.add(sideLedLeft);

    const sideLedRight = new THREE.Mesh(sideLedLeftGeo, cyanLedMat);
    sideLedRight.position.set(0.81, 0.05, 0);
    fuselageGroup.add(sideLedRight);

    // Dual RTK GNSS Antenna Pucks on rear deck
    const rtkGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.16, 16);
    const rtk1 = new THREE.Mesh(rtkGeo, titaniumMat);
    rtk1.position.set(-0.35, 0.46, -0.7);
    fuselageGroup.add(rtk1);

    const rtk2 = new THREE.Mesh(rtkGeo, titaniumMat);
    rtk2.position.set(0.35, 0.46, -0.7);
    fuselageGroup.add(rtk2);

    // PointLight on front nose for luminous volumetric sheen
    const noseLight = new THREE.PointLight(0x00d9ff, 3.2, 7.5);
    noseLight.position.set(0, 0.1, 1.4);
    fuselageGroup.add(noseLight);

    // Downward inspection spotlight cone
    const spotLight = new THREE.SpotLight(0x00d9ff, 4.5, 20, Math.PI / 7, 0.5, 1.2);
    spotLight.position.set(0, -0.2, 0.5);
    spotLight.target.position.set(0, -10, 3);
    fuselageGroup.add(spotLight);
    fuselageGroup.add(spotLight.target);

    // 5.2 Four Diagonal Carbon Rotor Arms
    const armConfigs = [
      { angle: Math.PI * 0.25, x: -1.6, z: 1.5, rotY: Math.PI * 0.25, isCw: true, port: true },
      { angle: -Math.PI * 0.25, x: 1.6, z: 1.5, rotY: -Math.PI * 0.25, isCw: false, port: false },
      { angle: Math.PI * 0.75, x: -1.8, z: -1.5, rotY: Math.PI * 0.75, isCw: false, port: true },
      { angle: -Math.PI * 0.75, x: 1.8, z: -1.5, rotY: -Math.PI * 0.75, isCw: true, port: false },
    ];

    const rotorBlades: { bladeGroup: THREE.Group; blurDisc: THREE.Mesh; isCw: boolean }[] = [];

    armConfigs.forEach((cfg) => {
      // Carbon arm tube
      const armLength = 1.9;
      const armGeo = new THREE.CylinderGeometry(0.08, 0.1, armLength, 12);
      const arm = new THREE.Mesh(armGeo, carbonDarkMat);
      arm.rotation.z = Math.PI / 2;
      arm.rotation.y = cfg.rotY;
      arm.position.set(cfg.x * 0.52, 0.02, cfg.z * 0.52);
      drone.add(arm);

      // Motor mount bracket at arm tip
      const mountGeo = new THREE.CylinderGeometry(0.24, 0.26, 0.28, 16);
      const mount = new THREE.Mesh(mountGeo, titaniumMat);
      mount.position.set(cfg.x, 0.12, cfg.z);
      drone.add(mount);

      // Motor cooling vents
      const motorBellGeo = new THREE.CylinderGeometry(0.2, 0.22, 0.22, 16);
      const motorBell = new THREE.Mesh(motorBellGeo, carbonAccentMat);
      motorBell.position.set(cfg.x, 0.26, cfg.z);
      drone.add(motorBell);

      // Navigation LED at arm tip (Red for port left, Green for starboard right)
      const navColor = cfg.port ? 0xef4444 : 0x10b981;
      const navLedGeo = new THREE.SphereGeometry(0.06, 8, 8);
      const navLedMat = new THREE.MeshBasicMaterial({ color: navColor });
      const navLed = new THREE.Mesh(navLedGeo, navLedMat);
      navLed.position.set(cfg.x * 1.05, 0.05, cfg.z * 1.05);
      drone.add(navLed);

      // Propeller Assembly Group (Spins at high speed)
      const propGroup = new THREE.Group();
      propGroup.position.set(cfg.x, 0.38, cfg.z);
      drone.add(propGroup);

      // Center Prop Nut Hub
      const hubGeo = new THREE.CylinderGeometry(0.08, 0.1, 0.1, 12);
      const hub = new THREE.Mesh(hubGeo, titaniumMat);
      propGroup.add(hub);

      // Dual aerodynamic propeller blades
      const bladeGeo = new THREE.BoxGeometry(2.1, 0.02, 0.16);
      const blade = new THREE.Mesh(bladeGeo, carbonDarkMat);
      propGroup.add(blade);

      // High-Speed Translucent Propeller Blur Disc (Matches Reference Motion Blur)
      const blurGeo = new THREE.CircleGeometry(1.15, 28);
      const blurDisc = new THREE.Mesh(blurGeo, propBlurMat);
      blurDisc.rotation.x = -Math.PI / 2;
      blurDisc.position.y = 0.01;
      propGroup.add(blurDisc);

      rotorBlades.push({
        bladeGroup: propGroup,
        blurDisc,
        isCw: cfg.isCw,
      });
    });

    // 5.3 Underslung 3-Axis Stabilized Camera Gimbal
    const gimbalBase = new THREE.Group();
    gimbalBase.position.set(0, -0.28, 0.45);
    drone.add(gimbalBase);

    // Vibration dampening plate
    const damperGeo = new THREE.CylinderGeometry(0.28, 0.28, 0.06, 16);
    const damper = new THREE.Mesh(damperGeo, carbonDarkMat);
    gimbalBase.add(damper);

    // Gimbal Pitch/Roll Bracket
    const gimbalArm = new THREE.Group();
    gimbalBase.add(gimbalArm);

    // Camera Spherical Pod (Inspection Payload)
    const cameraPodGeo = new THREE.SphereGeometry(0.38, 24, 24);
    const cameraPod = new THREE.Mesh(cameraPodGeo, titaniumMat);
    cameraPod.position.set(0, -0.32, 0);
    gimbalArm.add(cameraPod);

    // Main Optical Zoom Lens Element (Sapphire Blue Refraction)
    const lensGeo = new THREE.CylinderGeometry(0.18, 0.16, 0.18, 20);
    const lens = new THREE.Mesh(lensGeo, opticalGlassMat);
    lens.rotation.x = Math.PI / 2;
    lens.position.set(0, -0.32, 0.32);
    gimbalArm.add(lens);

    // Secondary FLIR Thermal Sensor Lens
    const flirGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.12, 16);
    const flir = new THREE.Mesh(flirGeo, carbonDarkMat);
    flir.rotation.x = Math.PI / 2;
    flir.position.set(0.16, -0.42, 0.28);
    gimbalArm.add(flir);

    // 5.4 Rugged Carbon Landing Skids
    const landingGear = new THREE.Group();
    landingGear.position.set(0, -0.35, 0);
    drone.add(landingGear);

    // Two longitudinal skids
    const skidGeo = new THREE.CylinderGeometry(0.05, 0.05, 2.6, 12);
    const leftSkid = new THREE.Mesh(skidGeo, carbonDarkMat);
    leftSkid.rotation.x = Math.PI / 2;
    leftSkid.position.set(-0.75, -0.55, 0);
    landingGear.add(leftSkid);

    const rightSkid = new THREE.Mesh(skidGeo, carbonDarkMat);
    rightSkid.rotation.x = Math.PI / 2;
    rightSkid.position.set(0.75, -0.55, 0);
    landingGear.add(rightSkid);

    // 4 Vertical Angled Skid Struts
    const strutGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.65, 8);
    const strutPositions = [
      { x: -0.75, z: 0.7, rotZ: -0.22 },
      { x: -0.75, z: -0.7, rotZ: -0.22 },
      { x: 0.75, z: 0.7, rotZ: 0.22 },
      { x: 0.75, z: -0.7, rotZ: 0.22 },
    ];
    strutPositions.forEach((sp) => {
      const strut = new THREE.Mesh(strutGeo, carbonDarkMat);
      strut.rotation.z = sp.rotZ;
      strut.position.set(sp.x * 0.85, -0.25, sp.z);
      landingGear.add(strut);
    });

    // --- 6. Starfield & Space Telemetry Particles ---
    const starCount = 140;
    const starGeo = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 35;
      starPositions[i + 1] = (Math.random() - 0.5) * 20;
      starPositions[i + 2] = -5 - Math.random() * 25;
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    const starMat = new THREE.PointsMaterial({
      color: 0xbae6fd,
      size: 0.12,
      transparent: true,
      opacity: 0.6,
    });
    const stars = new THREE.Points(starGeo, starMat);
    scene.add(stars);

    // --- 7. Mouse Parallax & Window Events (Non-blocking) ---
    const targetMouse = { x: 0, y: 0 };
    const currentMouse = { x: 0, y: 0 };

    const handlePointerMove = (e: MouseEvent) => {
      targetMouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      targetMouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };

    window.addEventListener('pointermove', handlePointerMove, { passive: true });

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    // --- 8. Animation Render Loop (Silky 60fps) ---
    let animId: number;
    const clock = new THREE.Clock();
    let pulseT = 0;

    const animate = () => {
      animId = requestAnimationFrame(animate);

      const elapsedTime = clock.getElapsedTime();
      pulseT += 0.012;

      // Smooth mouse interpolation (lerp)
      currentMouse.x += (targetMouse.x - currentMouse.x) * 0.05;
      currentMouse.y += (targetMouse.y - currentMouse.y) * 0.05;

      // 1. Organic Drone Hover Physics (Gentle bobbing & sway)
      const hoverY = Math.sin(elapsedTime * 1.6) * 0.14;
      const hoverPitch = Math.sin(elapsedTime * 1.1) * 0.035;
      const hoverRoll = Math.cos(elapsedTime * 0.9) * 0.025;

      // Base drone position + mouse parallax
      drone.position.x = 3.4 + currentMouse.x * 0.6;
      drone.position.y = 0.4 + hoverY + currentMouse.y * 0.4;
      drone.position.z = 2.0 - currentMouse.y * 0.5;

      // Dynamic 3D tilt response to cursor
      drone.rotation.x = 0.18 + hoverPitch - currentMouse.y * 0.25;
      drone.rotation.y = -0.42 + currentMouse.x * 0.35;
      drone.rotation.z = 0.04 + hoverRoll - currentMouse.x * 0.15;

      // 2. High-Speed Rotor Rotation & Propeller Dynamics
      const propSpeed = 0.85;
      rotorBlades.forEach((rotor) => {
        const direction = rotor.isCw ? 1 : -1;
        rotor.bladeGroup.rotation.y += propSpeed * direction;
        (rotor.blurDisc.material as THREE.MeshBasicMaterial).opacity =
          0.24 + Math.sin(elapsedTime * 8) * 0.04;
      });

      // 3. Gimbal Camera Gyro-Stabilization (Counters drone body tilt)
      gimbalArm.rotation.x = -hoverPitch * 0.8;
      gimbalArm.rotation.z = -hoverRoll * 0.8;

      // 4. Earth Globe Slow Rotation & Trajectory Pulse Packets
      earthMesh.rotation.y = -1.95 + elapsedTime * 0.008;

      arcCurves.forEach(({ curve, pulseMesh }, idx) => {
        const t = (pulseT + idx * 0.15) % 1;
        const pt = curve.getPoint(t);
        pulseMesh.position.copy(pt);
      });

      // 5. Starfield slow drift
      stars.rotation.y = elapsedTime * 0.002;

      renderer.render(scene, camera);
    };

    animate();

    // --- Cleanup ---
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('resize', handleResize);

      if (container && renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }

      renderer.dispose();
      earthGeo.dispose();
      earthMat.dispose();
      atmosGeo.dispose();
      atmosMat.dispose();
      starGeo.dispose();
      starMat.dispose();
    };
  }, []);

  return (
    <div
      ref={mountRef}
      className="drone-three-canvas-container"
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        overflow: 'hidden',
      }}
    />
  );
};
