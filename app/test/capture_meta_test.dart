import 'package:flutter_test/flutter_test.dart';
import 'package:kitchen_hand/capture_meta.dart';

void main() {
  group('needsCapture', () {
    test('a folder the importer just made still needs its text', () {
      // tools/import_instagram_saved.py writes exactly these two files.
      expect(
        needsCapture({
          'slug': 'ig-chef-mike-c-ab3xy',
          'files': ['meta.txt', 'url.txt'],
        }),
        isTrue,
      );
    });

    test('a folder with a pasted caption is done', () {
      expect(
        needsCapture({
          'slug': 'ig-chef-mike-c-ab3xy',
          'files': ['caption.txt', 'meta.txt', 'url.txt'],
        }),
        isFalse,
      );
    });

    test(
      'a youtube capture is done — fetch_youtube already wrote the text',
      () {
        expect(
          needsCapture({
            'slug': 'chengdu-tomato-egg-noodles',
            'files': ['url.txt', 'youtube.md'],
          }),
          isFalse,
        );
      },
    );

    test('a screenshot alone is not the recipe text', () {
      // The steps may be in the image, but nothing has been read out of it
      // yet — this still belongs in the queue.
      expect(
        needsCapture({
          'slug': 'ig-x-y',
          'files': ['meta.txt', 'screenshot.png', 'url.txt'],
        }),
        isTrue,
      );
    });

    test('a missing files key does not throw', () {
      expect(needsCapture({'slug': 'ig-x-y'}), isTrue);
    });
  });

  group('metaField', () {
    const meta = '''
input_type: instagram
creator: @chef.mike
source_url: https://www.instagram.com/p/C_aB3xy/
captured_date: 2026-09-17
saved_on: 2023-11-14
post_date: unknown

# saved_on is when you saved the post, not when it was published.
# creator: @not-this-one
''';

    test('reads the fields the importer writes', () {
      expect(metaField(meta, 'creator'), '@chef.mike');
      expect(
        metaField(meta, 'source_url'),
        'https://www.instagram.com/p/C_aB3xy/',
      );
      expect(metaField(meta, 'input_type'), 'instagram');
    });

    test('a commented-out key above the real one is not returned', () {
      // The real line must come second, or the loop returns before the
      // comment guard is ever reached and the test proves nothing.
      const shadowed = '# creator: @wrong\ncreator: @chef.mike';
      expect(metaField(shadowed, 'creator'), '@chef.mike');
    });

    test('a key that only appears commented out reads as absent', () {
      expect(metaField('# creator: @wrong', 'creator'), isNull);
      expect(
        metaField('  # source_url: https://x.test/', 'source_url'),
        isNull,
      );
    });

    test('a URL value keeps its own colons', () {
      expect(
        metaField('source_url: https://x.test/a:b', 'source_url'),
        'https://x.test/a:b',
      );
    });

    test('missing, empty and null all read as null', () {
      expect(metaField(meta, 'nope'), isNull);
      expect(metaField('creator:', 'creator'), isNull);
      expect(metaField('creator:    ', 'creator'), isNull);
      expect(metaField(null, 'creator'), isNull);
    });

    test('a hand-edited file with prose degrades instead of throwing', () {
      const messy = 'from Mom, no source\ncreator: Mom\nnot a key value line';
      expect(metaField(messy, 'creator'), 'Mom');
      expect(metaField(messy, 'source_url'), isNull);
    });
  });

  group('isValidSlug', () {
    test('matches the backend rule', () {
      expect(isValidSlug('chengdu-tomato-egg-noodles'), isTrue);
      expect(isValidSlug('ig-chef-mike-c-ab3xy'), isTrue);
      expect(isValidSlug('Chengdu'), isFalse);
      expect(isValidSlug('under_score'), isFalse);
      expect(isValidSlug('double--hyphen'), isFalse);
      expect(isValidSlug('-leading'), isFalse);
      expect(isValidSlug('trailing-'), isFalse);
      expect(isValidSlug(''), isFalse);
      expect(isValidSlug('../escape'), isFalse);
    });
  });

  group('textFieldForSource', () {
    test('routes each source to the file docs/ingestion.md names for it', () {
      expect(textFieldForSource('instagram'), 'caption');
      expect(textFieldForSource('tiktok'), 'transcript');
      expect(textFieldForSource('youtube'), 'transcript');
      expect(textFieldForSource('document'), 'raw');
      expect(textFieldForSource('pasted-text'), 'raw');
      expect(textFieldForSource('anything-else'), 'raw');
    });
  });
}
