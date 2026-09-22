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
  const supported = Boolean(localConstructor());
  const [available, setAvailable] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(false);
  const checkingRef = useRef(false);
  const mounted = useRef(true);
  const disabledRef = useRef(disabled);
  disabledRef.current = disabled;
  const [listening, setListening] = useState(false);
  const recognition = useRef<LocalRecognition | null>(null);
  const finalIndexes = useRef(new Set<number>());
  const callbacks=useRef({onTranscript,onError});callbacks.current={onTranscript,onError};

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      const instance = recognition.current;
      if (instance) {
        instance.onresult = null; instance.onerror = null; instance.onend = null;
        instance.stop();
      }
      recognition.current = null;
    };
  }, []);

  useEffect(() => {
    if (!disabled) return;
    const instance = recognition.current;
    if (instance) {
      instance.onresult = null; instance.onerror = null; instance.onend = null;
      instance.stop();
      recognition.current = null;
    }
    setListening(false);
  }, [disabled]);

  function stop() { recognition.current?.stop(); }
  async function start() {
    const Constructor = localConstructor();
    if (!Constructor?.available || disabledRef.current || checkingRef.current) return;
    checkingRef.current = true;
    setChecking(true);
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      // Query native speech only after a deliberate click: an exposed API does
      // not guarantee a working on-device service in an embedded browser.
      const status = await Promise.race([
        Constructor.available({ langs: [navigator.language || 'en-US'], processLocally: true }),
        new Promise<string>((_, reject) => { timer = setTimeout(() => reject(Error('timeout')), 5000); }),
      ]);
      if (!mounted.current || disabledRef.current) return;
      setAvailable(status === 'available');
      if (status !== 'available') {
        callbacks.current.onError('On-device speech for this language is not installed or available. You can keep typing; HQ will not use a cloud recognizer.');
        return;
      }
    } catch {
      if (mounted.current) callbacks.current.onError('Local speech support could not be checked. Your typed draft is unchanged.');
      return;
    } finally {
      clearTimeout(timer);
      checkingRef.current = false;
      if (mounted.current) setChecking(false);
    }
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

  const unavailable = checking ? 'Checking local voice support…' : !supported ? 'Local voice input is unavailable in this browser.' : available === false ? 'On-device speech for this language is unavailable. Click to check again.' : 'Click to check local voice support. No cloud recognition.';
  return <span className="voice-input">
    <button type="button" className="attach-button" aria-label={listening ? 'Stop voice input' : 'Start local voice input'} aria-pressed={listening} disabled={disabled || !supported || checking} title={available ? 'Local-only voice input' : unavailable} onClick={listening ? stop : start}>
      {listening ? <Square size={15} /> : <Mic size={15} />}<span>{listening ? 'Stop voice' : 'Voice'}</span>
    </button>
    <span className="sr-only" role="status" aria-live="polite">{listening ? 'Listening locally.' : available ? 'Local voice input ready.' : unavailable}</span>
  </span>;
}
