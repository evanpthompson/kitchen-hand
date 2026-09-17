import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/api_client.dart';
import '../capture_meta.dart';

/// Raw-paste capture (Phase C of docs/app-spec.md).
///
/// Built as a queue worker rather than a bare form, because the real job it
/// serves is a batch: tools/import_instagram_saved.py turns an Instagram
/// export into ~55 folders holding a permalink and nothing else, and each one
/// needs its caption pasted. A form you navigate to 55 times is the version
/// that does not get finished — so the screen tracks how many are left, opens
/// the post for you, and advances on save.
class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key, required this.api});
  final ApiClient api;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  final _textController = TextEditingController();
  final _metaController = TextEditingController();
  final _slugController = TextEditingController();

  List<Map<String, dynamic>> _queue = [];
  int _total = 0;
  String? _slug; // null == composing a brand-new capture
  String _sourceType = 'instagram';
  final List<CaptureUpload> _uploads = [];

  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadQueue();
  }

  @override
  void dispose() {
    _textController.dispose();
    _metaController.dispose();
    _slugController.dispose();
    super.dispose();
  }

  Future<void> _loadQueue() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final entries = (await widget.api.listInbox())
          .cast<Map<String, dynamic>>();
      final pending = entries.where(needsCapture).toList();
      setState(() {
        _queue = pending;
        _total = entries.length;
        _loading = false;
      });
      if (pending.isNotEmpty) {
        await _open(pending.first['slug'] as String);
      } else {
        setState(() => _slug = null);
      }
    } catch (e) {
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  /// Load an existing capture into the form.
  ///
  /// Pre-filling meta.txt is not a nicety: the importer writes the handle and
  /// permalink there, and saving a form whose meta box never loaded would post
  /// over them. Blank is dropped client- and server-side, so a failed load
  /// leaves the file alone rather than clearing it.
  Future<void> _open(String slug) async {
    setState(() {
      _slug = slug;
      _error = null;
      _uploads.clear();
      _textController.clear();
      _metaController.clear();
    });
    try {
      final capture = await widget.api.getInboxCapture(slug);
      final files = (capture['files'] as List).cast<Map<String, dynamic>>();
      String? contentOf(String name) {
        for (final f in files) {
          if (f['name'] == name) return f['content'] as String?;
        }
        return null;
      }

      final meta = contentOf('meta.txt');
      setState(() {
        _metaController.text = meta ?? '';
        final declared = metaField(meta, 'input_type');
        if (declared != null && sourceTypes.contains(declared)) {
          _sourceType = declared;
        }
      });
    } catch (e) {
      setState(() => _error = 'Could not load $slug: $e');
    }
  }

  void _startNewCapture() {
    setState(() {
      _slug = null;
      _slugController.clear();
      _textController.clear();
      _metaController.clear();
      _uploads.clear();
      _error = null;
    });
  }

  Future<void> _attach() async {
    // file_picker v13: pickFiles is static, returns [] on cancel, and bytes
    // come from readAsBytes() rather than a withData flag.
    final picked = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: const [
        'png',
        'jpg',
        'jpeg',
        'webp',
        'gif',
        'heic',
        'pdf',
        'txt',
        'md',
        'json',
      ],
    );
    if (picked.isEmpty) return;
    final added = <CaptureUpload>[];
    for (final f in picked) {
      added.add(CaptureUpload(filename: f.name, bytes: await f.readAsBytes()));
    }
    if (!mounted) return;
    setState(() => _uploads.addAll(added));
  }

  Future<void> _openPost() async {
    final url = metaField(_metaController.text, 'source_url');
    if (url == null) return;
    await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  Future<void> _save({required bool advance}) async {
    final slug = _slug ?? _slugController.text.trim();
    if (slug.isEmpty) {
      setState(() => _error = 'A slug is required.');
      return;
    }
    if (!isValidSlug(slug)) {
      setState(
        () => _error =
            'Invalid slug "$slug" — lowercase letters, digits and single '
            'hyphens only (e.g. chengdu-tomato-egg-noodles).',
      );
      return;
    }
    if (_textController.text.trim().isEmpty && _uploads.isEmpty) {
      setState(
        () => _error = 'Nothing to save — paste the text or attach a file.',
      );
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final field = textFieldForSource(_sourceType);
      await widget.api.captureFiles(
        slug,
        caption: field == 'caption' ? _textController.text : null,
        transcript: field == 'transcript' ? _textController.text : null,
        raw: field == 'raw' ? _textController.text : null,
        meta: _metaController.text,
        uploads: _uploads,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Saved $slug')));
      setState(() => _saving = false);
      if (advance) {
        await _loadQueue();
      } else {
        await _open(slug);
      }
    } catch (e) {
      setState(() {
        _saving = false;
        _error = '$e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final done = _total - _queue.length;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Capture'),
        actions: [
          TextButton.icon(
            onPressed: _startNewCapture,
            icon: const Icon(Icons.add),
            label: const Text('New'),
          ),
          IconButton(onPressed: _loadQueue, icon: const Icon(Icons.refresh)),
        ],
        bottom: _loading
            ? null
            : PreferredSize(
                preferredSize: const Size.fromHeight(28),
                child: _QueueProgress(done: done, total: _total),
              ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Row(
              children: [
                SizedBox(width: 260, child: _buildQueueList()),
                const VerticalDivider(width: 1),
                Expanded(child: _buildForm()),
              ],
            ),
    );
  }

  Widget _buildQueueList() {
    if (_queue.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'Nothing waiting for a paste.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    return ListView.builder(
      itemCount: _queue.length,
      itemBuilder: (context, i) {
        final slug = _queue[i]['slug'] as String;
        return ListTile(
          dense: true,
          selected: slug == _slug,
          title: Text(slug, style: const TextStyle(fontSize: 13)),
          onTap: () => _open(slug),
        );
      },
    );
  }

  Widget _buildForm() {
    final permalink = metaField(_metaController.text, 'source_url');
    final creator = metaField(_metaController.text, 'creator');
    final isNew = _slug == null;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (isNew)
          TextField(
            controller: _slugController,
            decoration: const InputDecoration(
              labelText: 'Slug',
              hintText: 'chengdu-tomato-egg-noodles',
              helperText: 'Lowercase, hyphen-separated. Creates inbox/<slug>/.',
            ),
          )
        else
          Row(
            children: [
              Expanded(
                child: Text(
                  _slug!,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              if (creator != null) Text(creator),
            ],
          ),
        const SizedBox(height: 12),
        Row(
          children: [
            DropdownButton<String>(
              value: _sourceType,
              onChanged: (v) => setState(() => _sourceType = v!),
              items: [
                for (final t in sourceTypes)
                  DropdownMenuItem(value: t, child: Text(t)),
              ],
            ),
            const SizedBox(width: 16),
            if (permalink != null)
              OutlinedButton.icon(
                onPressed: _openPost,
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Open post'),
              ),
          ],
        ),
        if (permalink != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: SelectableText(
              permalink,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        const SizedBox(height: 16),
        TextField(
          controller: _textController,
          maxLines: 16,
          minLines: 8,
          decoration: InputDecoration(
            labelText: switch (textFieldForSource(_sourceType)) {
              'caption' => 'Caption (saved as caption.txt)',
              'transcript' => 'Transcript (saved as transcript.txt)',
              _ => 'Raw text (saved as raw.txt)',
            },
            hintText:
                'Paste the recipe text, plus any comment that corrects it.',
            alignLabelWithHint: true,
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        ExpansionTile(
          title: const Text('meta.txt'),
          subtitle: const Text(
            'Handle, permalink, dates — written by the importer',
          ),
          tilePadding: EdgeInsets.zero,
          children: [
            TextField(
              controller: _metaController,
              maxLines: 10,
              minLines: 4,
              onChanged: (_) => setState(() {}), // refresh the permalink row
              decoration: const InputDecoration(border: OutlineInputBorder()),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            OutlinedButton.icon(
              onPressed: _attach,
              icon: const Icon(Icons.attach_file, size: 18),
              label: const Text('Attach screenshot'),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                _uploads.isEmpty
                    ? 'For carousel posts where the steps are in the image.'
                    : _uploads.map((u) => u.filename).join(', '),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Card(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_error!),
              ),
            ),
          ),
        const SizedBox(height: 24),
        Row(
          children: [
            FilledButton(
              onPressed: _saving ? null : () => _save(advance: true),
              child: Text(_saving ? 'Saving…' : 'Save & next'),
            ),
            const SizedBox(width: 12),
            TextButton(
              onPressed: _saving ? null : () => _save(advance: false),
              child: const Text('Save'),
            ),
          ],
        ),
      ],
    );
  }
}

/// Visible progress through the queue. A batch of 55 pastes with no counter
/// is a batch that feels infinite.
class _QueueProgress extends StatelessWidget {
  const _QueueProgress({required this.done, required this.total});
  final int done;
  final int total;

  @override
  Widget build(BuildContext context) {
    if (total == 0) return const SizedBox(height: 28);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$done of $total captured',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 4),
          LinearProgressIndicator(value: total == 0 ? 0 : done / total),
        ],
      ),
    );
  }
}
