import 'package:flutter/material.dart';
import '../api/api_client.dart';

const _imageExtensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'};

/// Inbox queue — folders in inbox/ not yet (or already) normalized into a
/// draft. Opening one shows the raw capture so you can read it side by
/// side while doing the normalize step yourself. See docs/app-spec.md.
class InboxScreen extends StatefulWidget {
  const InboxScreen({super.key, required this.api});
  final ApiClient api;

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.api.listInbox();
  }

  void _reload() {
    setState(() {
      _future = widget.api.listInbox();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Inbox'),
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
          final entries = snapshot.data!;
          if (entries.isEmpty) {
            return const Center(child: Text('Inbox is empty.'));
          }
          return ListView.builder(
            itemCount: entries.length,
            itemBuilder: (context, i) {
              final e = entries[i] as Map<String, dynamic>;
              return ListTile(
                leading: Icon(
                  e['has_draft'] == true
                      ? Icons.description
                      : Icons.inbox_outlined,
                ),
                title: Text(e['slug']),
                subtitle: Text(
                  '${e['source_type_guess']} · ${(e['files'] as List).length} file(s)'
                  '${e['has_draft'] == true ? ' · draft exists' : ''}',
                ),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) =>
                        InboxDetailScreen(api: widget.api, slug: e['slug']),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class InboxDetailScreen extends StatefulWidget {
  const InboxDetailScreen({super.key, required this.api, required this.slug});
  final ApiClient api;
  final String slug;

  @override
  State<InboxDetailScreen> createState() => _InboxDetailScreenState();
}

class _InboxDetailScreenState extends State<InboxDetailScreen> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.api.getInboxCapture(widget.slug);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.slug)),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          }
          final files = (snapshot.data!['files'] as List)
              .cast<Map<String, dynamic>>();
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              for (final f in files) _buildFile(context, f),
            ],
          );
        },
      ),
    );
  }

  Widget _buildFile(BuildContext context, Map<String, dynamic> f) {
    final name = f['name'] as String;
    final ext = name.contains('.')
        ? name.substring(name.lastIndexOf('.')).toLowerCase()
        : '';
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(name, style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (f['content'] != null)
              SelectableText(f['content'])
            else if (_imageExtensions.contains(ext))
              Image.network(
                widget.api.inboxFileUrl(widget.slug, name),
                errorBuilder: (context, error, stackTrace) =>
                    const Text('(image failed to load)'),
              )
            else
              Text('(binary file, ${f['size']} bytes)'),
          ],
        ),
      ),
    );
  }
}
