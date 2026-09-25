export type SpeechAvailability = 'unknown' | 'available' | 'downloadable' | 'downloading' | 'unavailable' | 'unsupported' | 'check-failed' | 'install-failed';

const KNOWN_AVAILABILITY = new Set<SpeechAvailability>(['available', 'downloadable', 'downloading', 'unavailable']);

export function normalizeAvailability(value: unknown): SpeechAvailability {
  return typeof value === 'string' && KNOWN_AVAILABILITY.has(value as SpeechAvailability)
    ? value as SpeechAvailability
    : 'unavailable';
}

/** English (US) is a reliable local-pack choice when a browser locale is unsupported. */
export function speechLanguages(browserLanguage?: string): string[] {
  const locale = browserLanguage?.trim();
  return locale && locale.toLowerCase() !== 'en-us' ? ['en-US', locale] : ['en-US'];
}

export function availabilityCopy(status: SpeechAvailability): string {
  switch (status) {
    case 'available': return 'On-device voice input is ready.';
    case 'downloadable': return 'An on-device language pack is available to install.';
    case 'downloading': return 'The on-device language pack is downloading.';
    case 'unsupported': return 'This browser does not provide local speech recognition.';
    case 'check-failed': return 'HQ could not check local speech support.';
    case 'install-failed': return 'The on-device language pack was not installed. You can try again or use macOS Dictation.';
    case 'unavailable': return 'No on-device language pack is available for this language.';
    default: return 'Check whether on-device voice input is available.';
  }
}
