import React, { useEffect, useRef, useState } from 'react';
import { Mic, Square } from 'lucide-react';

type VoiceInputProps = {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  onError: (message: string) => void;
};

type LocalRecognition = EventTarget & {
  continuous: boolean;
  interimResults: boolean;
  processLocally: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
};

type LocalRecognitionConstructor = {
  new (): LocalRecognition;
  available?: (options: { langs: string[]; processLocally: true }) => Promise<'available' | string>;
};

function localConstructor(): LocalRecognitionConstructor | null {
  const candidate = (globalThis as any).SpeechRecognition || (globalThis as any).webkitSpeechRecognition;
  return candidate && typeof candidate.available === 'function' && 'processLocally' in candidate.prototype ? candidate : null;
}

function errorMessage(code?: string) {
  if (code === 'not-allowed' || code === 'service-not-allowed') return 'Microphone permission was not granted.';
  if (code === 'no-speech') return 'No speech was detected. Try again when you are ready.';
  if (code === 'audio-capture') return 'No microphone is available.';
  return 'Local voice input could not start. Your typed draft is unchanged.';
}

/** Local-only Web Speech input. It never falls back to a cloud recognizer. */
export default function VoiceInput({ onTranscript, disabled = false, onError }: VoiceInputProps) {
  const [available, setAvailable] = useState(false);
  const [checking, setChecking] = useState(true);
  const [listening, setListening] = useState(false);
  const recognition = useRef<LocalRecognition | null>(null);
  const finalIndexes = useRef(new Set<number>());
  const callbacks=useRef({onTranscript,onError});callbacks.current={onTranscript,onError};

  useEffect(() => {
    let active = true;
    const Constructor = localConstructor();
    if (!Constructor?.available) { setChecking(false); return; }
    Constructor.available({ langs: [navigator.language || 'en-US'], processLocally: true })
      .then(status => { if (active) setAvailable(status === 'available'); })
      .catch(() => { if (active) setAvailable(false); })
      .finally(() => { if (active) setChecking(false); });
    return () => { active = false; const instance=recognition.current;if(instance){instance.onresult=null;instance.onerror=null;instance.onend=null;instance.stop();}recognition.current = null; };
  }, []);

  function stop() { recognition.current?.stop(); }
  function start() {
    const Constructor = localConstructor();
    if (!Constructor || !available || disabled) { onError('Local voice input is unavailable in this browser.'); return; }
    const instance = new Constructor();
    recognition.current = instance;
    finalIndexes.current.clear();
    instance.continuous = true;
    instance.interimResults = false;
    instance.processLocally = true;
    instance.lang = navigator.language || 'en-US';
    instance.onresult = event => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        if (event.results[index].isFinal && !finalIndexes.current.has(index)) {
          finalIndexes.current.add(index);
          callbacks.current.onTranscript(event.results[index][0].transcript);
        }
      }
    };
    instance.onerror = event => { setListening(false); callbacks.current.onError(errorMessage(event.error)); };
    instance.onend = () => { if (recognition.current === instance) recognition.current = null; setListening(false); };
    try { instance.start(); setListening(true); } catch { recognition.current = null; setListening(false); onError('Local voice input could not start. Your typed draft is unchanged.'); }
  }

  const unavailable = checking ? 'Checking local voice support…' : 'Local voice input is unavailable in this browser.';
  return <span className="voice-input">
    <button type="button" className="attach-button" aria-label={listening ? 'Stop voice input' : 'Start local voice input'} aria-pressed={listening} disabled={disabled || !available || checking} title={available ? 'Local-only voice input' : unavailable} onClick={listening ? stop : start}>
      {listening ? <Square size={15} /> : <Mic size={15} />}<span>{listening ? 'Stop voice' : 'Voice'}</span>
    </button>
    <span className="sr-only" role="status" aria-live="polite">{listening ? 'Listening locally.' : available ? 'Local voice input ready.' : unavailable}</span>
  </span>;
}
