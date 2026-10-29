import React from 'react';
import ReactDOM from 'react-dom/client';
import FullPage from './FullPage.tsx';
import '@/design/tokens.css';
import '@/ui/status.css';
import '@/ui/turns.css';
import './full.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <FullPage />
  </React.StrictMode>,
);
