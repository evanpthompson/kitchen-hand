import 'package:flutter/material.dart';
import '../api/api_client.dart';

/// Collection browser — read-only. Sanity-checks what's already in the
/// trusted collection (e.g. "does this already exist" before ingesting a
/// new one); not a cooking mode. See docs/app-spec.md.
class RecipesScreen extends StatefulWidget {
  const RecipesScreen({super.key, required this.api});
  final ApiClient api;

  @override
  State<RecipesScreen> createState() => _RecipesScreenState();
}

class _RecipesScreenState extends State<RecipesScreen> {
  late Future<List<dynamic>> _future;
  String? _tagFilter;
  List<String> _tags = [];

  @override
  void initState() {
    super.initState();
    _reload();
    widget.api.listTags().then((t) {
      if (mounted) setState(() => _tags = t.cast<String>());
    });
  }

  void _reload() {
    _future = widget.api.listRecipes();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Recipes')),
      body: Column(
        children: [
          if (_tags.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Wrap(
                spacing: 8,
                children: [
                  FilterChip(
                    label: const Text('All'),
                    selected: _tagFilter == null,
                    onSelected: (_) => setState(() => _tagFilter = null),
                  ),
                  for (final tag in _tags)
                    FilterChip(
                      label: Text(tag),
                      selected: _tagFilter == tag,
                      onSelected: (sel) =>
                          setState(() => _tagFilter = sel ? tag : null),
                    ),
                ],
              ),
            ),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(child: Text('Error: ${snapshot.error}'));
                }
                var recipes = snapshot.data!;
                if (_tagFilter != null) {
                  recipes = recipes
                      .where(
                        (r) => (r['tags'] as List).contains(_tagFilter),
                      )
                      .toList();
                }
                if (recipes.isEmpty) {
                  return const Center(child: Text('No recipes yet.'));
                }
                return ListView.builder(
                  itemCount: recipes.length,
                  itemBuilder: (context, i) {
                    final r = recipes[i] as Map<String, dynamic>;
                    return ListTile(
                      title: Text(r['title'] ?? r['slug']),
                      subtitle: Text(
                        [
                          if (r['cuisine'] != null) r['cuisine'],
                          if (r['mode'] != null) r['mode'],
                          if (r['servings'] != null) '${r['servings']} servings',
                        ].join(' · '),
                      ),
                      trailing: Wrap(
                        spacing: 4,
                        children: [
                          for (final tag in (r['tags'] as List))
                            Chip(
                              label: Text(tag, style: const TextStyle(fontSize: 11)),
                              visualDensity: VisualDensity.compact,
                            ),
                        ],
                      ),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => RecipeDetailScreen(
                            api: widget.api,
                            slug: r['slug'],
                          ),
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class RecipeDetailScreen extends StatefulWidget {
  const RecipeDetailScreen({super.key, required this.api, required this.slug});
  final ApiClient api;
  final String slug;

  @override
  State<RecipeDetailScreen> createState() => _RecipeDetailScreenState();
}

class _RecipeDetailScreenState extends State<RecipeDetailScreen> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.api.getRecipe(widget.slug);
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
          final r = snapshot.data!;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(r['title'] ?? '', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 4),
              Text(
                [
                  if (r['cuisine'] != null) r['cuisine'],
                  if (r['mode'] != null) 'mode: ${r['mode']}',
                  if (r['servings'] != null) '${r['servings']} servings',
                ].join(' · '),
                style: Theme.of(context).textTheme.bodySmall,
              ),
              if (r['source'] != null) ...[
                const SizedBox(height: 4),
                Text('Source: ${r['source']}', style: Theme.of(context).textTheme.bodySmall),
              ],
              const Divider(height: 32),
              Text('Ingredients', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              for (final ing in (r['ingredients'] as List? ?? []))
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    '• ${ing['quantity'] != null ? '${ing['quantity']} ' : ''}'
                    '${ing['name']}'
                    '${ing['prep'] != null ? ' (${ing['prep']})' : ''}',
                  ),
                ),
              const Divider(height: 32),
              Text('Phases', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              for (final (i, phase) in (r['phases'] as List? ?? []).indexed)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${i + 1}. ${phase['name']}',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      Text(phase['instruction'] ?? ''),
                    ],
                  ),
                ),
              if (r['notes'] != null) ...[
                const Divider(height: 32),
                Text('Notes', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Text(r['notes']),
              ],
            ],
          );
        },
      ),
    );
  }
}
