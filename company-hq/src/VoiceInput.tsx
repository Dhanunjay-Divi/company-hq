import React, { useEffect, useRef, useState } from 'react';
import { Mic, Square, X } from 'lucide-react';
import { availabilityCopy, normalizeAvailability, speechLanguages, type SpeechAvailability } from './speechAvailability';
import './voice-input.css';

type VoiceInputProps = {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  onError: (message: string) => void;
  /** Opens macOS Dictation setup and returns focus to the draft. It never sends audio to a cloud service. */
  onUseSystemDictation?: () => void | Promise<void>;
};

type LocalRecognition = EventTarget & {
  continuous: boolean;
  interimResults: boolean;
  processLocally: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

type LocalRecognitionConstructor = {
  new (): LocalRecognition;
  available?: (options: { langs: string[]; processLocally: true }) => Promise<string>;
  install?: (options: { langs: string[] }) => Promise<boolean>;
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
export default function VoiceInput({ onTranscript, disabled = false, onError, onUseSystemDictation }: VoiceInputProps) {
  const [availability, setAvailability] = useState<SpeechAvailability>('unknown');
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);
  const [language, setLanguage] = useState(() => speechLanguages(navigator.language)[0]);
  const [listening, setListening] = useState(false);
  const recognition = useRef<LocalRecognition | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const mounted = useRef(true);
  const disabledRef = useRef(disabled);
  const finalIndexes = useRef(new Set<number>());
  const callbacks = useRef({ onTranscript, onError });
  callbacks.current = { onTranscript, onError };
  disabledRef.current = disabled;

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
    if (setupOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [setupOpen]);

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

  async function checkLanguage(): Promise<SpeechAvailability> {
    const Constructor = localConstructor();
    if (!Constructor?.available) {
      if (mounted.current) setAvailability('unsupported');
      return 'unsupported';
    }
    setChecking(true);
    try {
      const status = normalizeAvailability(await Constructor.available({ langs: [language], processLocally: true }));
      if (mounted.current) setAvailability(status);
      return status;
    } catch {
      if (mounted.current) setAvailability('check-failed');
      return 'check-failed';
    } finally {
      if (mounted.current) setChecking(false);
    }
  }

  async function installLanguage() {
    const Constructor = localConstructor();
    if (!Constructor?.install) {
      setAvailability('install-failed');
      return;
    }
    setInstalling(true);
    try {
      const installed = await Constructor.install({ langs: [language] });
      if (!mounted.current) return;
      if (!installed) {
        setAvailability('install-failed');
        return;
      }
      await checkLanguage();
    } catch {
      if (mounted.current) setAvailability('install-failed');
    } finally {
      if (mounted.current) setInstalling(false);
    }
  }

  function stop() { recognition.current?.stop(); }

  async function start() {
    if (disabledRef.current || checking || installing) return;
    const status = await checkLanguage();
    if (status !== 'available' || disabledRef.current) {
      setSetupOpen(true);
      return;
    }
    const Constructor = localConstructor();
    if (!Constructor) return;
    const instance = new Constructor();
    recognition.current = instance;
    finalIndexes.current.clear();
    instance.continuous = true;
    instance.interimResults = false;
    instance.processLocally = true;
    instance.lang = language;
    instance.onresult = event => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        if (event.results[index].isFinal && !finalIndexes.current.has(index)) {
          finalIndexes.current.add(index);
          callbacks.current.onTranscript(event.results[index][0].transcript);
        }
      }
    };
    instance.onerror = event => { if (mounted.current) setListening(false); callbacks.current.onError(errorMessage(event.error)); };
    instance.onend = () => { if (recognition.current === instance) recognition.current = null; if (mounted.current) setListening(false); };
    try { instance.start(); setListening(true); } catch { recognition.current = null; setListening(false); callbacks.current.onError('Local voice input could not start. Your typed draft is unchanged.'); }
  }

  async function useSystemDictation() {
    try { await onUseSystemDictation?.(); }
    catch { callbacks.current.onError('macOS Keyboard settings could not be opened. Open System Settings manually.'); }
  }

  const unavailable = checking ? 'Checking local voice support…' : availabilityCopy(availability);
  const canInstall = availability === 'downloadable' && Boolean(localConstructor()?.install);
  const languages = speechLanguages(navigator.language);
  return <span className="voice-input">
    <button type="button" className="attach-button" aria-label={listening ? 'Stop voice input' : 'Set up or start local voice input'} aria-pressed={listening} disabled={disabled || checking || installing} title={listening ? 'Stop local voice input' : 'Local-only voice input'} onClick={listening ? stop : start}>
      {listening ? <Square size={15} aria-hidden="true" /> : <Mic size={15} aria-hidden="true" />}<span>{listening ? 'Stop voice' : 'Voice'}</span>
    </button>
    <span className="sr-only" role="status" aria-live="polite">{listening ? 'Listening locally.' : unavailable}</span>
    <dialog ref={dialog} className="voice-setup-dialog" aria-labelledby="voice-setup-title" onCancel={() => setSetupOpen(false)} onClick={event => { if (event.target === dialog.current) setSetupOpen(false); }}>
      <button type="button" className="icon-btn voice-setup-close" aria-label="Close voice input setup" onClick={() => setSetupOpen(false)}><X size={17} aria-hidden="true" /></button>
      <h2 id="voice-setup-title">Set up local voice input</h2>
      <p>HQ only uses on-device speech here. It will not switch to a cloud recognizer.</p>
      <label htmlFor="voice-language">Language<select id="voice-language" value={language} onChange={event => { setLanguage(event.target.value); setAvailability('unknown'); }} disabled={checking || installing}>{languages.map(value => <option key={value} value={value}>{value === 'en-US' ? 'English (United States)' : value}</option>)}</select></label>
      <p className="voice-setup-status" role="status" aria-live="polite">{unavailable}</p>
      {availability === 'available' && <button type="button" className="primary-button" onClick={() => { setSetupOpen(false); void start(); }}>Start local voice input</button>}
      {canInstall && <button type="button" className="primary-button" disabled={installing} onClick={() => void installLanguage()}>{installing ? 'Installing language pack…' : 'Install on-device language pack'}</button>}
      {availability !== 'available' && !canInstall && <button type="button" className="small-button" disabled={checking} onClick={() => void checkLanguage()}>{checking ? 'Checking…' : 'Check again'}</button>}
      {(availability === 'unsupported' || availability === 'unavailable' || availability === 'install-failed' || availability === 'check-failed') && <section className="voice-setup-help" aria-labelledby="system-dictation-title">
        <h3 id="system-dictation-title">Use macOS Dictation instead</h3>
        <ol><li>Enable Dictation in Keyboard settings.</li><li>Return to HQ and focus your draft.</li><li>Use your configured Dictation shortcut. Review the text before sending.</li></ol>
        {onUseSystemDictation && <button type="button" className="small-button" onClick={() => void useSystemDictation()}>Open Keyboard settings</button>}
      </section>}
      <menu><button type="button" className="small-button" onClick={() => setSetupOpen(false)}>Close</button></menu>
    </dialog>
  </span>;
}
