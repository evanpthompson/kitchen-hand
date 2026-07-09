import 'dart:convert';
import 'package:flutter/material.dart';
import '../api/api_client.dart';

const _jsonEncoder = JsonEncoder.withIndent('  ');

/// Draft review — the core screen. Shows validation errors and
/// provenance.extraction_notes prominently, lets you edit the draft
/// in place (as JSON, not per-field forms — see docs/app-spec.md's
/// v1 scope), and promotes/discards. Promote surfaces dedup candidates
/// rather than silently merging. See docs/ingestion.md for the review
/// checklist this screen exists to support.
class DraftsScreen extends StatefulWidget {
  const DraftsScreen({super.key, required this.api});
  final ApiClient api;

  @override
  State<DraftsScreen> createState() => _DraftsScreenState();
}

class _DraftsScreenState extends State<DraftsScreen> {
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    setState(() {
      _future = widget.api.listDrafts();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Drafts'),
        actions: [
          IconButton(onPressed: _reload, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: FutureBuilder<List<dynamic>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          final drafts = snapshot.data!;
          if (drafts.isEmpty) {
            return const Center(child: Text('No drafts awaiting review.'));
          }
          return ListView.builder(
            itemCount: drafts.length,
            itemBuilder: (context, i) {
              final d = drafts[i] as Map<String, dynamic>;
              final valid = d['valid'] == true;
              return ListTile(
                leading: Icon(
                  valid ? Icons.check_circle_outline : Icons.error_outline,
                  color: valid ? Colors.green : Colors.orange,
                ),
                title: Text(d['title'] ?? d['slug']),
                subtitle: Text(
                  [
                    if (d['mode'] != null) d['mode'],
                    valid ? 'schema valid' : '${(d['errors'] as List).length} schema error(s)',
                    if (d['has_extraction_notes'] == true) 'has extraction notes',
                  ].join(' · '),
                ),
                onTap: () async {
                  final changed = await Navigator.of(context).push<bool>(
                    MaterialPageRoute(
                      builder: (_) =>
                          DraftDetailScreen(api: widget.api, slug: d['slug']),
                    ),
                  );
                  if (changed == true) _reload();
                },
              );
            },
          );
        },
      ),
    );
  }
}

class DraftDetailScreen extends StatefulWidget {
  const DraftDetailScreen({super.key, required this.api, required this.slug});
  final ApiClient api;
  final String slug;

  @override
  State<DraftDetailScreen> createState() => _DraftDetailScreenState();
}

class _DraftDetailScreenState extends State<DraftDetailScreen> {
  late Future<void> _loadFuture;
  late TextEditingController _controller;
  List<String> _errors = [];
  String? _extractionNotes;
  bool _busy = false;
  bool _dirtySinceLastSave = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _loadFuture = _load();
  }

  Future<void> _load() async {
    final draft = await widget.api.getDraft(widget.slug);
    final data = draft['data'] as Map<String, dynamic>;
    _controller.text = _jsonEncoder.convert(data);
    _errors = (draft['errors'] as List).cast<String>();
    final provenance = data['provenance'];
    _extractionNotes = provenance is Map ? provenance['extraction_notes'] as String? : null;
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      final data = jsonDecode(_controller.text) as Map<String, dynamic>;
      final result = await widget.api.saveDraft(widget.slug, data);
      setState(() {
        _errors = (result['errors'] as List).cast<String>();
        _dirtySinceLastSave = false;
        final provenance = data['provenance'];
        _extractionNotes = provenance is Map ? provenance['extraction_notes'] as String? : null;
      });
      _showSnack('Saved.');
    } on FormatException catch (e) {
      _showSnack('Invalid JSON: ${e.message}');
    } catch (e) {
      _showSnack('Save failed: $e');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _promote({bool force = false}) async {
    if (_dirtySinceLastSave) {
      _showSnack('Save your edits before promoting.');
      return;
    }
    setState(() => _busy = true);
    try {
      final result = await widget.api.promoteDraft(widget.slug, force: force);
      if (result['promoted'] == true) {
        if (mounted) Navigator.of(context).pop(true);
        return;
      }
      if (result['reason'] == 'dedup_candidates_found') {
        final candidates = (result['candidates'] as List).cast<Map<String, dynamic>>();
        final proceed = await _showDedupDialog(candidates);
        if (proceed == true) {
          await _promote(force: true);
          return;
        }
      }
    } on ApiException catch (e) {
      _showSnack('Promote blocked: ${e.detail}');
    } catch (e) {
      _showSnack('Promote failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool?> _showDedupDialog(List<Map<String, dynamic>> candidates) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Possible duplicate found'),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('This looks similar to an existing recipe:'),
              const SizedBox(height: 12),
              for (final c in candidates)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    '${c['title']} (${c['slug']})\n'
                    'title similarity: ${c['title_similarity']}, '
                    'ingredient similarity: ${c['ingredient_similarity']}',
                  ),
                ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Promote anyway (keep both)'),
          ),
        ],
      ),
    );
  }

  Future<void> _discard() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard draft?'),
        content: Text(
          'This deletes recipes/_drafts/${widget.slug}.yaml. '
          'The raw capture in inbox/ is not affected.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await widget.api.discardDraft(widget.slug);
      if (mounted) Navigator.of(context).pop(true);
    }
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.slug),
        actions: [
          IconButton(
            onPressed: _busy ? null : _discard,
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Discard',
          ),
        ],
      ),
      body: FutureBuilder<void>(
        future: _loadFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          return Column(
            children: [
              if (_extractionNotes != null && _extractionNotes!.trim().isNotEmpty)
                Container(
                  width: double.infinity,
                  color: Colors.amber.shade100,
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Extraction notes',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Text(_extractionNotes!),
                    ],
                  ),
                ),
              if (_errors.isNotEmpty)
                Container(
                  width: double.infinity,
                  color: Colors.red.shade50,
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${_errors.length} schema error(s)',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          color: Colors.red,
                        ),
                      ),
                      for (final e in _errors) Text('• $e'),
                    ],
                  ),
                ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: TextField(
                    controller: _controller,
                    maxLines: null,
                    expands: true,
                    style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
                    decoration: const InputDecoration(border: OutlineInputBorder()),
                    onChanged: (_) => _dirtySinceLastSave = true,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(12),
                child: Wrap(
                  spacing: 8,
                  children: [
                    FilledButton.icon(
                      onPressed: _busy ? null : _save,
                      icon: const Icon(Icons.save),
                      label: const Text('Save'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _busy ? null : () => _promote(),
                      icon: const Icon(Icons.check),
                      label: const Text('Promote'),
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
