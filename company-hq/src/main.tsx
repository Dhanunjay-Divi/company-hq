import './styles.css';
import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './Workbench';
import {Provider as TooltipProvider} from '@radix-ui/react-tooltip';
createRoot(document.getElementById('root')!).render(<TooltipProvider><App/></TooltipProvider>);
