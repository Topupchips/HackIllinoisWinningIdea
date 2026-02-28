import { useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoadingScreen from './components/LoadingScreen';
import Simulator from './components/Simulator';
import './App.css';

function App() {
  const [loadingComplete, setLoadingComplete] = useState(false);

  const handleLoadingComplete = useCallback(() => {
    setLoadingComplete(true);
  }, []);

  return (
    <BrowserRouter>
      {!loadingComplete ? (
        <LoadingScreen onComplete={handleLoadingComplete} duration={2400} />
      ) : (
        <div className="app-content">
          <Routes>
            <Route path="/" element={<Simulator />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      )}
    </BrowserRouter>
  );
}

export default App;
