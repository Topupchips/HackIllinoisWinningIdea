import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface Molecule3DProps {
  atomCount: number;
}

export default function Molecule3D({ atomCount }: Molecule3DProps) {
  const group = useRef<THREE.Group>(null);

  useFrame((_, delta) => {
    if (group.current) {
      group.current.rotation.y += delta * 0.5;
    }
  });

  const count = Math.min(Math.max(atomCount, 3), 10);
  const positions: [number, number, number][] = [];
  const radius = 0.35;

  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2 + Math.random() * 0.2;
    positions.push([
      Math.cos(angle) * radius,
      (Math.random() - 0.5) * 0.25,
      Math.sin(angle) * radius,
    ]);
  }

  const colors = ['#14b8a6', '#0d9488', '#2dd4bf'];

  return (
    <group ref={group}>
      {positions.map((pos, i) => (
        <mesh key={i} position={pos}>
          <sphereGeometry args={[0.07, 12, 12]} />
          <meshStandardMaterial
            color={colors[i % colors.length]}
            metalness={0.3}
            roughness={0.6}
          />
        </mesh>
      ))}
    </group>
  );
}
