import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Download, Ellipsis, FolderOpen, RotateCcw, Trash2 } from 'lucide-react';
import './chat-menu.css';

type Props = {
  name: string;
  trashed?: boolean;
  onExport: (kind: 'json' | 'markdown') => void;
  onReveal: () => void;
  onDelete: () => void;
  onRestore: () => void;
};

export default function ChatMenu({name, trashed=false, onExport, onReveal, onDelete, onRestore}: Props) {
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({left:12,top:60});
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const rect=button.current?.getBoundingClientRect();
    if(rect) setPosition({left:Math.max(12,Math.min(rect.left,window.innerWidth-266)),top:Math.max(12,Math.min(rect.bottom+5,window.innerHeight-(trashed?66:190)))});
    requestAnimationFrame(()=>menu.current?.querySelector<HTMLButtonElement>('button')?.focus());
    const dismiss = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node) && !menu.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); button.current?.focus(); } };
    document.addEventListener('pointerdown', dismiss); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('keydown', escape); };
  }, [open]);
  const choose = (action: () => void) => { setOpen(false); action(); };
  return <div className="chat-menu" ref={root} onClick={event => event.stopPropagation()}>
    <button ref={button} className="chat-menu-trigger" aria-label={`Chat actions for ${name}`} aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen(value => !value)}><Ellipsis size={18}/></button>
    {open && createPortal(<div ref={menu} style={{position:'fixed',left:position.left,top:position.top}} className="chat-menu-popover" role="menu" aria-label={`Chat actions for ${name}`} onKeyDown={event=>{if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;event.preventDefault();const items=Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('button')||[]);const index=items.indexOf(document.activeElement as HTMLButtonElement);const next=event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;items[next]?.focus()}}>
      {trashed ? <button role="menuitem" onClick={() => choose(onRestore)}><RotateCcw size={16} aria-hidden="true"/>Restore chat</button> : <>
        <button role="menuitem" onClick={() => choose(() => onExport('markdown'))}><Download size={16} aria-hidden="true"/>Export Markdown</button>
        <button role="menuitem" onClick={() => choose(() => onExport('json'))}><Download size={16} aria-hidden="true"/>Export JSON</button>
        <button role="menuitem" onClick={() => choose(onReveal)}><FolderOpen size={16} aria-hidden="true"/>Show project folder in Finder</button>
        <button role="menuitem" className="danger" onClick={() => choose(onDelete)}><Trash2 size={16} aria-hidden="true"/>Delete chat</button>
      </>}
    </div>,document.body)}
  </div>;
}
