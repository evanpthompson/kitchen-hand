/// Pure helpers for the capture screen — no Flutter imports, so they can be
/// unit-tested without pumping widgets.
library;

/// Capture files that mean "this folder already has its recipe text".
/// A folder holding only url.txt/meta.txt is what
/// tools/import_instagram_saved.py leaves behind: bookkeeping, no recipe yet.
const contentFiles = {
  'caption.txt',
  'transcript.txt',
  'raw.txt',
  'youtube.md',
  'jsonld.json',
};

/// Does this inbox entry still need its text pasted in?
bool needsCapture(Map<String, dynamic> entry) {
  final files = (entry['files'] as List? ?? const []).cast<String>().toSet();
  return files.intersection(contentFiles).isEmpty;
}

/// Read one `key: value` line out of an inbox meta.txt.
///
/// Deliberately not a YAML parse: meta.txt is a human scratchpad that is
/// allowed to hold prose and `#` comments, and a strict parser would throw on
/// a file somebody hand-edited rather than degrade to "field not found".
///
/// Full-line `#` comments need no special case — the `#` is parsed as part of
/// the key, so `# creator: @x` yields the key `"# creator"` and never matches
/// a lookup for `creator`. An explicit skip was tried here and removed as dead
/// code; capture_meta_test.dart pins the behaviour so it stays correct.
String? metaField(String? meta, String key) {
  if (meta == null) return null;
  for (final line in meta.split('\n')) {
    final trimmed = line.trim();
    final sep = trimmed.indexOf(':');
    if (sep <= 0) continue;
    if (trimmed.substring(0, sep).trim() != key) continue;
    final value = trimmed.substring(sep + 1).trim();
    return value.isEmpty ? null : value;
  }
  return null;
}

final _slugPattern = RegExp(r'^[a-z0-9]+(-[a-z0-9]+)*$');

/// Mirrors core.is_valid_slug in the backend. Checked client-side only to
/// give a useful message before the round trip — the backend still refuses.
bool isValidSlug(String slug) => _slugPattern.hasMatch(slug);

/// Which file a source type's main text box writes to, matching the field
/// names POST /inbox/{slug}/files accepts.
String textFieldForSource(String sourceType) {
  switch (sourceType) {
    case 'tiktok':
    case 'youtube':
      return 'transcript';
    case 'instagram':
      return 'caption';
    default:
      return 'raw';
  }
}

const sourceTypes = [
  'instagram',
  'tiktok',
  'document',
  'pasted-text',
  'url',
  'other',
];
