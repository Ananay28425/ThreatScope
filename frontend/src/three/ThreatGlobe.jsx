/**
 * ThreatGlobe — Three.js 3D visualization of the node network.
 *
 * Renders a dark Earth sphere with glowing node markers positioned
 * at geo-coordinates (simulated). When a node emits a high-score signal,
 * an animated pulse ripples outward from its position.
 *
 * Node colour state:
 *   Normal:     #00bfff (blue)
 *   Suspicious: #ffa500 (amber)
 *   Attack:     #ff2244 (red)
 *
 * Built with @react-three/fiber (declarative Three.js for React).
 * All animation is driven by useFrame (runs in WebGL, not JS event loop).
 */

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import * as THREE from "three";
import { useThreatStore } from "../store/threatStore.js";

// ── Simulated node positions (lat/lon → 3D sphere surface) ───────────────────

const SIMULATED_NODES = [
  { id: "org_1",  lat: 40.7128,  lon: -74.006  },   // New York
  { id: "org_2",  lat: 51.5074,  lon: -0.1278  },   // London
  { id: "org_3",  lat: 35.6762,  lon: 139.6503 },   // Tokyo
  { id: "org_4",  lat: 28.6139,  lon: 77.209   },   // Delhi
  { id: "org_5",  lat: -33.8688, lon: 151.2093 },   // Sydney
  { id: "org_6",  lat: 48.8566,  lon: 2.3522   },   // Paris
  { id: "org_7",  lat: 55.7558,  lon: 37.6173  },   // Moscow
  { id: "org_8",  lat: -23.5505, lon: -46.6333 },   // São Paulo
  { id: "org_9",  lat: 1.3521,   lon: 103.8198 },   // Singapore
  { id: "org_10", lat: 19.0760,  lon: 72.8777  },   // Mumbai
];

function latLonToVec3(lat, lon, radius = 2.0) {
  const phi   = (90 - lat)  * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
     radius * Math.cos(phi),
     radius * Math.sin(phi) * Math.sin(theta),
  );
}

// ── Node Marker ───────────────────────────────────────────────────────────────

function NodeMarker({ nodeId, lat, lon }) {
  const meshRef = useRef();
  const ringRef = useRef();
  const nodes   = useThreatStore((s) => s.nodes);
  const state   = nodes[nodeId];

  const color = useMemo(() => {
    if (!state) return "#00bfff";
    if (state.anomaly_score >= 0.80) return "#ff2244";
    if (state.anomaly_score >= 0.50) return "#ffa500";
    return "#00bfff";
  }, [state?.anomaly_score]);

  const position = useMemo(() => latLonToVec3(lat, lon), [lat, lon]);

  useFrame((_, delta) => {
    if (!ringRef.current) return;
    // Pulse ring animation
    ringRef.current.scale.x += delta * 0.8;
    ringRef.current.scale.y += delta * 0.8;
    ringRef.current.scale.z += delta * 0.8;
    ringRef.current.material.opacity -= delta * 0.6;
    if (ringRef.current.material.opacity <= 0) {
      ringRef.current.scale.set(1, 1, 1);
      ringRef.current.material.opacity = state?.is_active ? 0.9 : 0;
    }
  });

  return (
    <group position={position}>
      {/* Node dot */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.025, 8, 8]} />
        <meshBasicMaterial color={color} />
      </mesh>
      {/* Pulse ring */}
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.03, 0.045, 16]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={state?.is_active ? 0.9 : 0}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

// ── Globe ─────────────────────────────────────────────────────────────────────

function Globe() {
  const globeRef = useRef();

  useFrame((_, delta) => {
    if (globeRef.current) {
      globeRef.current.rotation.y += delta * 0.04; // slow auto-rotate
    }
  });

  return (
    <group ref={globeRef}>
      {/* Earth sphere */}
      <mesh>
        <sphereGeometry args={[2.0, 64, 64]} />
        <meshPhongMaterial
          color="#0a1628"
          emissive="#0a1628"
          wireframe={false}
          transparent
          opacity={0.95}
        />
      </mesh>

      {/* Wireframe overlay */}
      <mesh>
        <sphereGeometry args={[2.005, 32, 32]} />
        <meshBasicMaterial color="#1a3a5c" wireframe transparent opacity={0.15} />
      </mesh>

      {/* Node markers */}
      {SIMULATED_NODES.map((node) => (
        <NodeMarker key={node.id} nodeId={node.id} lat={node.lat} lon={node.lon} />
      ))}
    </group>
  );
}

// ── Scene ─────────────────────────────────────────────────────────────────────

export default function ThreatGlobe() {
  return (
    <Canvas
      camera={{ position: [0, 0, 5.5], fov: 45 }}
      style={{ background: "transparent" }}
    >
      <ambientLight intensity={0.3} />
      <pointLight position={[10, 10, 10]} intensity={1.0} />
      <pointLight position={[-10, -10, -10]} color="#1e40af" intensity={0.5} />

      <Stars radius={80} depth={50} count={3000} factor={3} saturation={0} fade />

      <Globe />

      <OrbitControls
        enableZoom
        enablePan={false}
        minDistance={3}
        maxDistance={9}
        autoRotate={false}
      />
    </Canvas>
  );
}
