import React, { useId, useRef } from 'react';
import { ImagePlus, X } from 'lucide-react';
import './images.css';

export type ImageDraft = { id: string; name: string; mimeType: 'image/png' | 'image/jpeg' | 'image/webp'; dataBase64: string; previewUrl: string };
const supported = new Set(['image/png', 'image/jpeg', 'image/webp']);
const maxBytes = 6 * 1024 * 1024;
const maxImages = 4;

function createId() { return globalThis.crypto?.randomUUID?.() || `image-${Date.now()}-${Math.random().toString(16).slice(2)}`; }
function fileData(file: File) { return new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => typeof reader.result === 'string' ? resolve(reader.result) : reject(new Error('Could not read image.')); reader.onerror = () => reject(new Error(`Could not read ${file.name}.`)); reader.readAsDataURL(file); }); }
export async function readImageFiles(files: FileList | File[] | null | undefined, existing = 0): Promise<{ items: ImageDraft[]; errors: string[] }> {
  const accepted: File[] = [], errors: string[] = [];
  for (const file of Array.from(files || [])) { if (accepted.length + existing >= maxImages) { errors.push(`You can attach up to ${maxImages} images.`); break; } if (!supported.has(file.type)) { errors.push(`${file.name} must be PNG, JPEG, or WebP.`); continue; } if (file.size > maxBytes) { errors.push(`${file.name} is larger than 6 MiB.`); continue; } accepted.push(file); }
  const items = await Promise.all(accepted.map(async file => { const dataBase64 = await fileData(file); return { id: createId(), name: file.name || 'image', mimeType: file.type as ImageDraft['mimeType'], dataBase64: dataBase64.slice(dataBase64.indexOf(',')+1), previewUrl: dataBase64 }; }));
  return { items, errors };
}
export function useImageDrafts(initial: ImageDraft[] = []) { const [images, setImages] = React.useState(initial); return { images, setImages, clearImages: () => setImages([]) }; }
export default function ImageAttachments({ images, onChange, disabled = false, onError }: { images: ImageDraft[]; onChange: (images: ImageDraft[]) => void; disabled?: boolean; onError?: (message: string) => void }) {
  const input = useRef<HTMLInputElement>(null); const inputId = useId();
  async function add(files: FileList | File[] | null | undefined) { try { const result = await readImageFiles(files, images.length); if (result.items.length) onChange([...images, ...result.items]); result.errors.forEach(message => onError?.(message)); } catch(e) {onError?.(e instanceof Error ? e.message : 'Could not read image.')} }
  return <div className="image-attachments" onDragOver={event => { event.preventDefault(); }} onDrop={event => { event.preventDefault(); event.stopPropagation(); if (!disabled) add(event.dataTransfer.files); }}>
    <input ref={input} id={inputId} className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={disabled} onChange={event => { add(event.target.files); event.currentTarget.value = ''; }} />
    <button type="button" className="attach-button" onClick={() => input.current?.click()} disabled={disabled} aria-label="Attach images"><ImagePlus size={15} />Attach images</button>
    {images.length > 0 && <ul className="image-draft-list" aria-label={`${images.length} image attachment${images.length === 1 ? '' : 's'}`}>{images.map(image => <li key={image.id}><img src={image.previewUrl} alt={image.name} /><span>{image.name}</span><button type="button" aria-label={`Remove ${image.name}`} disabled={disabled} onClick={() => onChange(images.filter(item => item.id !== image.id))}><X size={13} /></button></li>)}</ul>}
  </div>;
}
