import './styles.css';
import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './Workbench';
import RecoveryBoundary from './RecoveryBoundary';
import {Provider as TooltipProvider} from '@radix-ui/react-tooltip';
createRoot(document.getElementById('root')!).render(<RecoveryBoundary><TooltipProvider><App/></TooltipProvider></RecoveryBoundary>);
