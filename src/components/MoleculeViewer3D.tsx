import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import Molecule3D from './Molecule3D';
import './MoleculeViewer3D.css';

interface MoleculeViewer3DProps {
  atomCount: number;
}

export default function MoleculeViewer3D({ atomCount }: MoleculeViewer3DProps) {
  return (
    <div className="molecule-viewer-3d">
      <Canvas
        camera={{ position: [0, 0, 1.5], fov: 50 }}
        gl={{ alpha: true, antialias: true }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[1, 1, 1]} intensity={0.8} />
        <Suspense fallback={null}>
          <Molecule3D atomCount={atomCount} />
        </Suspense>
      </Canvas>
    </div>
  );
}
