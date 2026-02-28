import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export default function DNAHelix3D() {
  const group = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (group.current) {
      group.current.rotation.y += delta * 0.3;
    }
  });

  const { tube1, tube2, bases1, bases2 } = useMemo(() => {
    const segments = 24;
    const radius = 0.4;
    const points: THREE.Vector3[] = [];
    for (let i = 0; i <= segments; i++) {
      const t = (i / segments) * Math.PI * 4;
      points.push(new THREE.Vector3(Math.cos(t) * radius, i * 0.15 - 1.8, Math.sin(t) * radius));
    }
    const points2: THREE.Vector3[] = [];
    for (let i = 0; i <= segments; i++) {
      const t = (i / segments) * Math.PI * 4 + Math.PI;
      points2.push(new THREE.Vector3(Math.cos(t) * radius, i * 0.15 - 1.8, Math.sin(t) * radius));
    }
    return {
      tube1: new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 32, 0.03, 8, false),
      tube2: new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points2), 32, 0.03, 8, false),
      bases1: points,
      bases2: points2,
    };
  }, []);

  return (
    <group ref={group} scale={0.6}>
      <mesh geometry={tube1}>
        <meshStandardMaterial color="#14b8a6" metalness={0.3} roughness={0.6} />
      </mesh>
      <mesh geometry={tube2}>
        <meshStandardMaterial color="#0d9488" metalness={0.3} roughness={0.6} />
      </mesh>
      {bases1.map((p, i) => (
        <mesh key={i} position={p}>
          <sphereGeometry args={[0.06, 8, 8]} />
          <meshStandardMaterial color="#2dd4bf" metalness={0.2} roughness={0.8} />
        </mesh>
      ))}
      {bases2.map((p, i) => (
        <mesh key={`b-${i}`} position={p}>
          <sphereGeometry args={[0.06, 8, 8]} />
          <meshStandardMaterial color="#2dd4bf" metalness={0.2} roughness={0.8} />
        </mesh>
      ))}
    </group>
  );
}
