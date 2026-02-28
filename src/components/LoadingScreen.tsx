import { useEffect } from 'react';
import { Dna } from 'lucide-react';
import './LoadingScreen.css';

interface LoadingScreenProps {
  onComplete: () => void;
  duration?: number;
}

export default function LoadingScreen({ onComplete, duration = 2400 }: LoadingScreenProps) {
  useEffect(() => {
    const timer = setTimeout(onComplete, duration);
    return () => clearTimeout(timer);
  }, [duration, onComplete]);

  return (
    <div className="loading-screen">
      <div className="loading-bg">
        <div className="loading-rings" />
        <div className="loading-glow" />
      </div>
      <div className="loading-logo">
        <Dna size={140} strokeWidth={1.25} />
      </div>
    </div>
  );
}
